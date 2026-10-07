"""Read-only mailbox adapters. OAuth always opens the system browser."""

import base64
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import quote
from uuid import uuid4

import httpx
import msal
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as GoogleCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from sqlalchemy import select

from job_tracker.credentials import Credentials
from job_tracker.db import Account
from job_tracker.domain import now, timestamp
from job_tracker.services import Tracker

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GRAPH_SCOPES = ["https://graph.microsoft.com/Mail.Read", "https://graph.microsoft.com/User.Read"]


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self.hidden += 1
        if tag in ("p", "br", "div", "li"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("style", "script"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def normalize(body: str, html: bool = False) -> str:
    if html:
        parser = TextExtractor()
        parser.feed(body)
        body = "".join(parser.parts)
    # Keep original message evidence but drop quoted reply chains and common signatures.
    body = re.split(r"(?m)^On .{1,200}wrote:\s*$|^-----Original Message-----|^-- \s*$", body)[0]
    return re.sub(r"\n{3,}", "\n\n", body).strip()[:16000]


@dataclass
class Email:
    provider_id: str
    thread_id: str
    sender: str
    subject: str
    body: str
    received_at: str


def register(tracker: Tracker, provider: str, address: str, reference: str, client_id: str = ""):
    with tracker.db.sessions.begin() as session:
        row = session.scalar(
            select(Account).where(Account.provider == provider, Account.address == address)
        )
        if row is None:
            row = Account(
                provider=provider,
                address=address,
                credential_ref=reference,
                client_id=client_id,
                last_sync=now(),
            )
            session.add(row)
        else:
            row.credential_ref, row.client_id = reference, client_id


def connect_gmail(tracker: Tracker, vault: Credentials, config: dict, persist: bool):
    if persist:
        vault.backend()  # Fail before opening a consent flow if secure storage is unavailable.
    installed = config.get("installed")
    if not installed or not installed.get("client_id", "").endswith(".apps.googleusercontent.com"):
        raise ValueError("Choose a Google OAuth client JSON for a Desktop application.")
    installed = dict(installed)
    installed.update(
        auth_uri="https://accounts.google.com/o/oauth2/auth",
        token_uri="https://oauth2.googleapis.com/token",
    )
    flow = InstalledAppFlow.from_client_config(
        {"installed": installed}, [GMAIL_SCOPE], autogenerate_code_verifier=True
    )
    token = flow.run_local_server(
        host="127.0.0.1",
        port=0,
        timeout_seconds=180,
        authorization_prompt_message="",
        prompt="consent",
    )
    with httpx.Client(timeout=30) as client:
        response = client.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/profile",
            headers={"Authorization": f"Bearer {token.token}"},
        )
        response.raise_for_status()
        address = response.json()["emailAddress"]
    reference = "gmail-" + uuid4().hex
    info = json.loads(token.to_json()) | {"_persist": persist}
    vault.save(reference, json.dumps(info), persist)
    register(tracker, "gmail", address, reference)
    return address


def microsoft_app(client_id: str, saved: str = ""):
    cache = msal.SerializableTokenCache()
    if saved:
        cache.deserialize(saved)
    app = msal.PublicClientApplication(
        client_id, authority="https://login.microsoftonline.com/common", token_cache=cache
    )
    return app, cache


def connect_outlook(tracker: Tracker, vault: Credentials, client_id: str, persist: bool):
    if persist:
        vault.backend()
    from uuid import UUID

    UUID(client_id)  # Public installed-app registration; never an application secret.
    app, cache = microsoft_app(client_id)
    result = app.acquire_token_interactive(scopes=GRAPH_SCOPES, timeout=180)
    if "access_token" not in result:
        raise ValueError("Microsoft sign-in did not complete. Check the app registration.")
    with httpx.Client(timeout=30) as client:
        response = client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {result['access_token']}"},
        )
        response.raise_for_status()
        profile = response.json()
        address = profile.get("mail") or profile["userPrincipalName"]
    reference = "outlook-" + uuid4().hex
    vault.save(reference, json.dumps({"cache": cache.serialize(), "_persist": persist}), persist)
    register(tracker, "outlook", address, reference, client_id)
    return address


class Mailbox:
    def __init__(self, account: dict, vault: Credentials):
        self.account, self.vault = account, vault

    def headers(self) -> dict:
        info = json.loads(self.vault.get(self.account["credential_ref"]) or "{}")
        if not info:
            raise ValueError("Reconnect the mailbox in Settings.")
        if self.account["provider"] == "gmail":
            credentials = GoogleCredentials.from_authorized_user_info(info, [GMAIL_SCOPE])
            if not credentials.valid:
                credentials.refresh(Request())
                self.vault.save(
                    self.account["credential_ref"],
                    json.dumps(
                        json.loads(credentials.to_json()) | {"_persist": info.get("_persist", True)}
                    ),
                    info.get("_persist", True),
                )
            token = credentials.token
        else:
            app, cache = microsoft_app(self.account["client_id"], info["cache"])
            accounts = app.get_accounts(username=self.account["address"]) or app.get_accounts()
            result = (
                app.acquire_token_silent(GRAPH_SCOPES, account=accounts[0]) if accounts else None
            )
            if not result or "access_token" not in result:
                raise ValueError("Reconnect your Microsoft mailbox in Settings.")
            if cache.has_state_changed:
                self.vault.save(
                    self.account["credential_ref"],
                    json.dumps(
                        {"cache": cache.serialize(), "_persist": info.get("_persist", True)}
                    ),
                    info.get("_persist", True),
                )
            token = result["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        if self.account["provider"] == "outlook":
            headers["Prefer"] = 'IdType="ImmutableId"'
        return headers

    def list_ids(self, start: str, end: str, cancelled=lambda: False) -> list[str]:
        headers = self.headers()
        ids, page = [], ""
        with httpx.Client(timeout=30) as client:
            while not cancelled():
                if self.account["provider"] == "gmail":
                    from datetime import datetime

                    since = int(datetime.fromisoformat(start).timestamp())
                    until = int(datetime.fromisoformat(end).timestamp())
                    url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
                    params = {
                        "q": f"after:{since} before:{until} -in:spam -in:trash",
                        "maxResults": 500,
                    }
                    if page:
                        params["pageToken"] = page
                    response = client.get(url, headers=headers, params=params)
                    response.raise_for_status()
                    data = response.json()
                    ids.extend(row["id"] for row in data.get("messages", []))
                    page = data.get("nextPageToken", "")
                else:
                    url = page or "https://graph.microsoft.com/v1.0/me/messages"
                    params = (
                        None
                        if page
                        else {
                            "$filter": f"receivedDateTime ge {start} and receivedDateTime lt {end}",
                            "$select": "id",
                            "$top": 500,
                        }
                    )
                    if not url.startswith("https://graph.microsoft.com/"):
                        raise ValueError("Invalid mailbox pagination URL.")
                    response = client.get(url, headers=headers, params=params)
                    response.raise_for_status()
                    data = response.json()
                    ids.extend(row["id"] for row in data.get("value", []))
                    page = data.get("@odata.nextLink", "")
                if len(ids) > 50000:
                    raise ValueError("More than 50,000 emails found. Choose a smaller date range.")
                if not page:
                    return ids
        return ids

    def get(self, provider_id: str) -> Email:
        headers = self.headers()
        with httpx.Client(timeout=30) as client:
            if self.account["provider"] == "gmail":
                response = client.get(
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages/"
                    + quote(provider_id, safe=""),
                    headers=headers,
                    params={"format": "full"},
                )
                response.raise_for_status()
                data = response.json()
                meta = {row["name"].lower(): row["value"] for row in data["payload"]["headers"]}
                plain, html = [], []

                def decode(part):
                    if part.get("filename"):
                        return  # Attachments are never opened or executed.
                    value = part.get("body", {}).get("data")
                    if value and part.get("mimeType") in ("text/plain", "text/html"):
                        content = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
                        target = plain if part["mimeType"] == "text/plain" else html
                        target.append(content.decode("utf-8", errors="replace"))
                    for nested in part.get("parts", []):
                        decode(nested)

                decode(data["payload"])
                from datetime import UTC, datetime

                received = datetime.fromtimestamp(int(data["internalDate"]) / 1000, UTC).isoformat()
                return Email(
                    provider_id,
                    data.get("threadId", ""),
                    meta.get("from", "")[:300],
                    meta.get("subject", "")[:300],
                    normalize("\n".join(plain or html), html=not plain),
                    timestamp(received),
                )
            response = client.get(
                "https://graph.microsoft.com/v1.0/me/messages/" + quote(provider_id, safe=""),
                headers=headers,
                params={"$select": "id,conversationId,from,subject,body,receivedDateTime"},
            )
            response.raise_for_status()
            data = response.json()
            return Email(
                provider_id,
                data.get("conversationId", ""),
                data.get("from", {}).get("emailAddress", {}).get("address", "")[:300],
                data.get("subject", "")[:300],
                normalize(
                    data["body"]["content"], html=data["body"]["contentType"].lower() == "html"
                ),
                timestamp(data["receivedDateTime"]),
            )
