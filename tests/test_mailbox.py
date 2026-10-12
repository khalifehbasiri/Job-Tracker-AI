import base64

import httpx
import pytest

from job_tracker.email import Mailbox, select_body


def test_html_supplies_rejection_missing_from_plaintext_footer():
    plain = (
        "Your update from Acme\nThis email was intended for Candidate\nhttps://tracking.example/"
    )
    html = (
        "<p>Your application to Software Engineer at Acme</p>"
        "<p>Thank you for applying. Unfortunately, we will not be moving forward "
        "with your application at this time.</p>"
        "<p>This email was intended for Candidate</p>"
        "<script>secret script content</script>"
    )
    body = select_body([plain], [html])
    assert "Unfortunately" in body
    assert "Software Engineer" in body
    assert "<p>" not in body and "secret script content" not in body


def test_full_plaintext_is_preferred_over_equivalent_html():
    plain = "We received your application for Engineer at Acme. Thank you for applying."
    assert select_body([plain], [f"<p>{plain}</p>"]) == plain


def test_short_plaintext_is_not_replaced_by_html_tracking_footer():
    plain = "We received your application."
    html = (
        "<p>We received your application.</p><p>This email was intended for Candidate</p>"
        "<p>"
        + "<a href='https://example.org'>Unsubscribe from all our promotional emails</a>" * 20
        + "</p>"
    )
    assert select_body([plain], [html]) == plain


def test_gmail_decodes_declared_charset(monkeypatch):
    def handle(request):
        text = "Nous avons reçu votre candidature."
        return httpx.Response(
            200,
            json={
                "internalDate": "1790856000000",
                "payload": {
                    "mimeType": "text/plain",
                    "headers": [
                        {"name": "Content-Type", "value": "text/plain; charset=iso-8859-1"}
                    ],
                    "body": {"data": base64.urlsafe_b64encode(text.encode("iso-8859-1")).decode()},
                },
            },
        )

    mailbox = adapter(monkeypatch, "gmail", handle)
    assert mailbox.get("one").body == "Nous avons reçu votre candidature."


def adapter(monkeypatch, provider, handle):
    # Real provider endpoints/scopes are exercised through a local HTTP transport only.
    client_type = httpx.Client
    transport = httpx.MockTransport(handle)
    monkeypatch.setattr(
        "job_tracker.email.httpx.Client",
        lambda **kwargs: client_type(transport=transport, **kwargs),
    )
    mailbox = Mailbox({"provider": provider}, None)
    mailbox.headers = lambda: {
        "Authorization": "Bearer fake-token",
        "Prefer": 'IdType="ImmutableId"',
    }
    return mailbox


def test_gmail_pagination_and_attachment_exclusion(monkeypatch):
    requests = []

    def handle(request):
        requests.append(request)
        if request.url.path.endswith("/messages"):
            page = request.url.params.get("pageToken")
            return httpx.Response(
                200,
                json={
                    "messages": [{"id": "2" if page else "1"}],
                    **({} if page else {"nextPageToken": "next"}),
                },
            )

        def encoded(value):
            return base64.urlsafe_b64encode(value.encode()).decode()

        return httpx.Response(
            200,
            json={
                "threadId": "thread",
                "internalDate": "1790856000000",
                "payload": {
                    "headers": [{"name": "Subject", "value": "Interview"}],
                    "parts": [
                        {
                            "mimeType": "text/html",
                            "body": {
                                "data": encoded(
                                    "<p>Interview invitation</p><script>hidden</script>"
                                )
                            },
                        },
                        {
                            "mimeType": "text/plain",
                            "filename": "private.txt",
                            "body": {"data": encoded("Attachment content")},
                        },
                    ],
                },
            },
        )

    mailbox = adapter(monkeypatch, "gmail", handle)
    assert mailbox.list_ids("2026-10-01T00:00:00+00:00", "2026-11-01T00:00:00+00:00") == ["1", "2"]
    assert "-in:spam -in:trash" in requests[0].url.params["q"]
    assert requests[1].url.params["pageToken"] == "next"
    message = mailbox.get("1")
    assert message.body == "Interview invitation"
    assert message.received_at == "2026-10-01T12:00:00+00:00"
    assert all(request.method == "GET" for request in requests)


def test_outlook_rejects_foreign_pagination_host(monkeypatch):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={"value": [], "@odata.nextLink": "https://graph.microsoft.com.evil.example/token"},
        )

    mailbox = adapter(monkeypatch, "outlook", handle)
    with pytest.raises(ValueError, match="pagination"):
        mailbox.list_ids("2026-10-01T00:00:00+00:00", "2026-11-01T00:00:00+00:00")
    assert len(requests) == 1


def test_outlook_reads_body_without_writes(monkeypatch):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "id/encoded",
                "conversationId": "thread",
                "subject": "Update",
                "from": {"emailAddress": {"address": "jobs@example.org"}},
                "receivedDateTime": "2026-10-01T12:00:00Z",
                "body": {"contentType": "html", "content": "<p>Thank you</p>"},
            },
        )

    mailbox = adapter(monkeypatch, "outlook", handle)
    message = mailbox.get("id/encoded")
    assert message.body == "Thank you"
    assert requests[0].method == "GET"
    assert requests[0].headers["Prefer"] == 'IdType="ImmutableId"'
    assert requests[0].url.raw_path.split(b"?")[0].endswith(b"id%2Fencoded")


def test_mailbox_read_retries_transient_error_then_recovers(monkeypatch):
    attempts = []
    monkeypatch.setattr("job_tracker.email.time.sleep", lambda _delay: None)

    def handle(request):
        attempts.append(request)
        if len(attempts) < 3:
            return httpx.Response(503, json={"error": {"message": "PRIVATE"}})
        return httpx.Response(
            200,
            json={
                "internalDate": "1790856000000",
                "payload": {"headers": [{"name": "Subject", "value": None}], "body": None},
            },
        )

    mailbox = adapter(monkeypatch, "gmail", handle)
    message = mailbox.get("id")
    assert len(attempts) == 3
    assert message.subject == "" and message.body == ""
