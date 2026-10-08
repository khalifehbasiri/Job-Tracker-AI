"""Actionable diagnostics from exception types/statuses, never private response text."""

import httpx
from google.auth.exceptions import RefreshError, TransportError
from openai import APIConnectionError, APIStatusError, APITimeoutError
from sqlalchemy.exc import SQLAlchemyError


class UserFacingError(ValueError):
    """Only raise with an application-authored, non-private message."""


class ReviewRequired(UserFacingError):
    """An unusable AI result is terminal for automatic processing, not a paid retry."""

    def __init__(self, reason, extraction=None):
        super().__init__(reason)
        self.extraction = extraction


class AutoRetryExhausted(UserFacingError):
    """Pause the scan after bounded recovery, rather than retrying each queued email."""


def openai_error_details(error: APIStatusError) -> tuple[str, str]:
    body = error.body if isinstance(error.body, dict) else {}
    details = body.get("error") if isinstance(body.get("error"), dict) else body
    return tuple(
        details.get(field) if isinstance(details.get(field), str) else ""
        for field in ("code", "type")
    )


def openai_quota_error(error: APIStatusError) -> bool:
    code, kind = openai_error_details(error)
    return (
        code
        in {
            "insufficient_quota",
            "billing_hard_limit_reached",
            "billing_not_active",
            "usage_limit_reached",
            "organization_quota_exceeded",
        }
        or kind == "insufficient_quota"
    )


def describe_error(error: Exception) -> str:
    if isinstance(error, UserFacingError):
        return str(error)
    if isinstance(error, APITimeoutError):
        return "OpenAI timed out. Saved progress is kept."
    if isinstance(error, APIConnectionError):
        return "Cannot reach OpenAI. Check your connection."
    if isinstance(error, APIStatusError):
        status = error.status_code
        if status >= 500:
            return f"OpenAI is temporarily unavailable (HTTP {status}). Saved progress is kept."
        if status == 429 and openai_quota_error(error):
            return "OpenAI API credits or quota are unavailable. Check API billing/limits."
        code, kind = openai_error_details(error)
        if status == 429 and (
            code in {"rate_limit_exceeded", "slow_down"} or kind == "rate_limit_error"
        ):
            return "OpenAI rate limit reached. Saved progress is kept."
        messages = {
            400: "OpenAI rejected the request format. Please report this application error.",
            401: "OpenAI rejected your API key. Replace or test it in Settings.",
            403: "OpenAI denied access. Check your project permissions and model access.",
            404: "The requested OpenAI model or endpoint is unavailable to your project.",
            429: "OpenAI rate or quota limit reached. Check API billing/limits, then resume.",
        }
        return messages.get(status, f"OpenAI returned HTTP {status}. Saved progress is kept.")
    if isinstance(error, RefreshError):
        return "Your Google authorization expired or was revoked. Reconnect Gmail in Settings."
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        messages = {
            401: "Mailbox authorization is no longer valid. Reconnect the account in Settings.",
            403: "Mailbox access was denied. Check read-only permissions or provider limits.",
            404: "An email is no longer available. It may have been removed during the scan.",
            429: "Mailbox rate limit reached. Wait briefly, then resume the scan.",
        }
        return messages.get(
            status, f"The mailbox provider returned HTTP {status}. Resume to retry."
        )
    if isinstance(error, (httpx.TimeoutException, TimeoutError)):
        return "The mailbox request timed out. Saved progress is kept; resume to retry."
    if isinstance(error, (httpx.RequestError, TransportError)):
        return "Cannot reach the mailbox provider. Check your connection, then resume."
    if isinstance(error, SQLAlchemyError):
        return (
            "The local database could not save this change. Check available disk space and access."
        )
    if isinstance(error, (KeyError, TypeError, AttributeError)):
        return (
            f"Unexpected application response ({type(error).__name__}). Please report this error."
        )
    if isinstance(error, ValueError):
        return "The record or provider response could not be validated. Check setup or retry."
    return "An unexpected error interrupted the operation. Saved scan progress is kept."


def blocks_scan(error: Exception) -> bool:
    if isinstance(error, AutoRetryExhausted):
        return True
    if isinstance(error, (APIStatusError, APIConnectionError, RefreshError, TransportError)):
        return True  # Do not repeat account-wide failures across hundreds of paid requests.
    if isinstance(error, (httpx.RequestError, SQLAlchemyError)):
        return True
    if isinstance(error, httpx.HTTPStatusError):
        return (
            error.response.status_code in (401, 403, 408, 429) or error.response.status_code >= 500
        )
    return False
