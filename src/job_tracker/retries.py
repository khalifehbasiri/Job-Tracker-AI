"""Conservative AI recovery policy; all dispatch/billing stays in the import worker."""

import math
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from random import uniform

from openai import APIConnectionError, APIStatusError

from job_tracker.errors import openai_error_details, openai_quota_error

MAX_AI_ATTEMPTS = 4
MAX_RETRY_AFTER_SECONDS = 120


def transient_ai_error(error: Exception) -> bool:
    if isinstance(error, APIConnectionError):
        return True  # Includes APITimeoutError; response/usage may be unknown.
    if not isinstance(error, APIStatusError) or openai_quota_error(error):
        return False
    if error.response.headers.get("x-should-retry", "").lower() == "false":
        return False
    if error.status_code in (408, 409) or 500 <= error.status_code < 600:
        return True
    if error.status_code == 429:
        code, kind = openai_error_details(error)
        # Unknown 429s may be billing failures; require an explicit rate-limit code/type.
        return code in {"rate_limit_exceeded", "slow_down"} or kind == "rate_limit_error"
    return False


def retry_after_seconds(error: Exception) -> float | None:
    if not isinstance(error, APIStatusError):
        return None
    headers = error.response.headers
    for name, divisor in (("retry-after-ms", 1000), ("retry-after", 1)):
        value = headers.get(name)
        if value is None:
            continue
        try:
            delay = float(value) / divisor
        except ValueError:
            continue
        if delay == math.inf and value.strip().lower() not in (
            "inf",
            "+inf",
            "infinity",
            "+infinity",
        ):
            return MAX_RETRY_AFTER_SECONDS + 1  # Numeric overflow means a long server wait.
        if math.isfinite(delay) and delay >= 0:
            return delay
    try:
        moment = parsedate_to_datetime(headers.get("retry-after", ""))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        return max(0, (moment - datetime.now(UTC)).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return None


def retry_delay(error: Exception, failed_attempt: int) -> float | None:
    requested = retry_after_seconds(error)
    if requested is not None and requested > MAX_RETRY_AFTER_SECONDS:
        return None  # Pause instead of sending earlier than the provider requested.
    backoff = 2 ** min(failed_attempt, MAX_AI_ATTEMPTS) + uniform(0, 1)
    return max(backoff, requested or 0)
