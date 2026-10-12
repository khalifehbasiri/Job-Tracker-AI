"""Remove redundant tracker work in a fixed window without touching the mailbox."""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select

from job_tracker.db import Application, ApplicationEvent, Message
from job_tracker.domain import timestamp
from job_tracker.evidence import EVIDENCE_REVIEW, latest_body, normalized_spans, source_excerpt
from job_tracker.matching import company_key, formatted_identity, role_key

WINDOW = timedelta(minutes=20)
ROUTINE_NOTICE = re.compile(
    r"\b(?:email (?:preferences|communications)|communication preferences|"
    r"privacy (?:notice|policy)|your application (?:was|has been) viewed|"
    r"(?:candidate|applicant) (?:account|profile) (?:has been |was )?created)\b",
    re.I,
)
REQUIRED_ACTION = re.compile(
    r"\b(?:verify|verification|action required|required action|"
    r"confirm your (?:email|address|account)|complete your application|"
    r"problem (?:with|completing)|unable to submit|"
    r"assessment|interview|offer|rejection|rejected|deadline|"
    r"(?:reply|respond) (?:to|by)|(?:must|need to|required to))\b",
    re.I,
)


@dataclass(frozen=True)
class FilterDecision:
    application_id: int
    representative_message_id: int
    reason: str


def is_routine_notice(message: Message) -> bool:
    body = latest_body(message.body)
    opening = next((line.strip() for line in body.splitlines() if line.strip()), "")
    # A privacy/preferences link in a footer does not make the email a routine notice.
    notice = ROUTINE_NOTICE.search(formatted_identity(message.subject)) or ROUTINE_NOTICE.search(
        formatted_identity(opening)
    )
    text = formatted_identity(message.subject + "\n" + body)
    return bool(notice and not REQUIRED_ACTION.search(text))


def supported_identity(message: Message, extraction: dict) -> bool:
    text = normalized_spans(
        message.sender + "\n" + message.subject + "\n" + latest_body(message.body)
    )[0].casefold()
    for field in ("company", "role", "requisition_id"):
        if extraction.get(field):
            needle = normalized_spans(extraction[field])[0].strip().casefold()
            if not re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", text):
                return False
    return True


def redundant_email(
    session,
    message: Message,
    result: dict,
    search_id: int,
    app: Application | None,
    match_reason: str = "",
) -> FilterDecision | None:
    """A validated confirmation anchors the window; filtered siblings never extend it."""
    kind = result.get("kind")
    if kind not in ("application", "other") or not message.received_at:
        return None
    if any(
        type(result.get(f)) not in (int, float) or not 0.9 <= result[f] <= 1
        for f in ("probability", "confidence")
    ):
        return None
    if "conflict" in match_reason or "multiple" in match_reason.casefold():
        return None
    ex = result.get("extraction") or {}
    if ex.get("deadline_at") or ex.get("interview_at"):
        return None
    if result.get("review_reason") not in (None, EVIDENCE_REVIEW):
        return None
    if kind == "application":
        if app is None or result.get("review_reason"):
            return None
        if REQUIRED_ACTION.search(latest_body(message.body)) or not supported_identity(message, ex):
            return None
        if not source_excerpt(message.body, ex.get("evidence") or ""):
            return None
        if ex.get("applied_on") and ex["applied_on"] != app.applied_on:
            return None
    elif not is_routine_notice(message) or not supported_identity(message, ex):
        return None
    # An explicit different company/title is not a sibling, even when its thread matches.
    if app is not None and (
        (ex.get("company") and company_key(ex["company"]) != company_key(app.company))
        or (ex.get("role") and role_key(ex["role"]) != role_key(app.role))
    ):
        return None
    if app is None and not ex.get("company"):
        return None
    current = datetime.fromisoformat(timestamp(message.received_at))
    anchors = []
    rows = session.execute(
        select(ApplicationEvent, Application, Message)
        .join(Application, Application.id == ApplicationEvent.application_id)
        .join(Message, Message.id == ApplicationEvent.message_id)
        .where(
            Application.search_id == search_id,
            ApplicationEvent.kind == "application",
            Message.account_id == message.account_id,
            Message.id != message.id,
        )
    )
    for _event, candidate, original in rows:
        if not original.received_at:
            continue
        if abs(current - datetime.fromisoformat(timestamp(original.received_at))) > WINDOW:
            continue
        if app is not None:
            if candidate.id != app.id:
                continue
        else:
            if company_key(candidate.company) != company_key(ex["company"]):
                continue
            if ex.get("role") and role_key(candidate.role) != role_key(ex["role"]):
                continue
            if ex.get("requisition_id") and formatted_identity(ex["requisition_id"]) != (
                formatted_identity(candidate.requisition_id)
            ):
                continue
        anchors.append((candidate.id, original.id, timestamp(original.received_at)))
    if len({candidate_id for candidate_id, _, _ in anchors}) != 1:
        return None
    chosen = min(anchors, key=lambda row: row[2])
    label = "Repeated application confirmation" if kind == "application" else "Routine notice"
    return FilterDecision(
        chosen[0], chosen[1], label + " within 20 minutes of a confirmation for this application."
    )
