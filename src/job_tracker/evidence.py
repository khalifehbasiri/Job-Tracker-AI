"""Ground evidence in source spans, tolerating email presentation differences."""

import re
from html import unescape

EVIDENCE_REVIEW = "AI evidence did not match the email text. Confirm the proposed fields manually."
PRESENTATION = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'})
EVENT_PATTERNS = {
    "application": (
        r"\b(?:we (?:have )?(?:successfully )?received your application|"
        r"your application (?:has been |was )?(?:received|submitted|sent)|"
        r"(?:acknowledge|acknowledging) receipt of your application|"
        r"thank(?:s| you)(?: again)? for (?:applying|submitting your application|"
        r"(?:successfully )?completing your application|your application|"
        r"taking the time to apply))\b"
    ),
    "rejection": (
        r"\b(?:we (?:have )?(?:decided|chosen) (?:not to (?:move|proceed)|"
        r"to (?:move forward|proceed) with (?:other|another))|"
        r"(?:we|we regret to inform you that we) (?:will not|won't|are unable to) "
        r"(?:be (?:moving|proceeding)|move|proceed)|"
        r"your application (?:was|has been) (?:unsuccessful|rejected)|"
        r"you (?:have not been|were not) selected|"
        r"we have not selected you to move forward)\b"
    ),
    "assessment": (
        r"\b(?:(?:invite|inviting|invited) you to (?:complete|take) (?:an? |the )?"
        r"(?:\w+ ){0,3}(?:assessment|test)|"
        r"please complete (?:an? |the |your )?(?:\w+ ){0,3}(?:assessment|test)|"
        r"your (?:\w+ ){0,3}assessment (?:is due|deadline)|"
        r"you were previously invited to take this challenge)\b"
    ),
    "interview": (
        r"\b(?:(?:invite|inviting|invited) you (?:to|for) (?:an? |the )?"
        r"(?:\w+ ){0,3}interview|"
        r"(?:schedule|scheduling|arrange) (?:an? |your |the )?(?:\w+ ){0,3}interview|"
        r"your interview (?:is scheduled|has been scheduled|is confirmed)|"
        r"thank you (?:again )?for the interview invitation)\b"
    ),
    "offer": r"\b(?:pleased|delighted) to offer you (?:the |a |an )?(?:position|role|job)\b",
}


def normalized_spans(text: str):
    """Map decoded entities and collapsed whitespace back to the untouched body."""
    chars, spans = [], []
    for token in re.finditer(r"&(?:#\d+|#x[\da-fA-F]+|[a-zA-Z]+);|.", text, re.DOTALL):
        for char in unescape(token.group()).translate(PRESENTATION):
            if char.isspace():
                if chars and chars[-1] == " ":
                    spans[-1] = (spans[-1][0], token.end())
                    continue
                char = " "
            chars.append(char)
            spans.append((token.start(), token.end()))
    return "".join(chars), spans


def source_excerpt(body: str, proposed: str) -> str:
    """Accept formatting equivalents, never summaries or noncontiguous excerpts."""
    needle = normalized_spans(proposed)[0].strip()
    if not needle:
        return ""
    text, spans = normalized_spans(body)
    start = text.find(needle)
    if start < 0:
        return ""
    return body[spans[start][0] : spans[start + len(needle) - 1][1]]


def latest_body(body: str) -> str:
    # A confirmation email may also advertise unrelated roles below the update.
    return re.split(
        r"(?im)^\s*(?:On [\s\S]{1,300}?wrote:|-----Original Message-----|"
        r"Begin forwarded message:|From:\s|>|"
        r"View similar jobs|Now, take these next steps)",
        body,
        maxsplit=1,
    )[0]


def recover_event_evidence(message, result: dict) -> dict | None:
    """Recover an erased/unsupported excerpt only from a literal, explicit event.

    The caller still enforces confidence, identity matching, and conflict checks.
    Every supplied identity field must occur in the latest body or subject. Dates
    from the rejected extraction are dropped because event evidence cannot prove them.
    """
    pattern = EVENT_PATTERNS.get(result.get("kind"))
    extraction = result.get("extraction") or {}
    if not pattern:
        return None
    body = latest_body(message.body)
    text, spans = normalized_spans(body)
    identity_text = normalized_spans(message.subject + "\n" + body)[0].casefold()
    for field in ("company", "role", "requisition_id"):
        value = extraction.get(field)
        if value:
            needle = normalized_spans(value)[0].strip().casefold()
            if not re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", identity_text):
                return None
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    if result["kind"] == "application" and any(
        re.search(other, text, re.IGNORECASE)
        for kind, other in EVENT_PATTERNS.items()
        if kind != "application"
    ):
        return None  # A receipt quoted within a later update must not reopen an application.
    evidence = body[spans[match.start()][0] : spans[match.end() - 1][1]]
    repaired = dict(result)
    repaired.pop("review_reason", None)
    repaired["extraction"] = extraction | {
        "evidence": evidence,
        "applied_on": None,
        "deadline_at": None,
        "interview_at": None,
    }
    repaired["evidence_source"] = "local_explicit_event"
    return repaired
