"""Validated records and deterministic application status rules."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class Stage(StrEnum):
    APPLIED = "Applied"
    ASSESSMENT = "Assessment"
    INTERVIEW = "Interview"
    OFFER = "Offer"


class Outcome(StrEnum):
    ACTIVE = "Active"
    REJECTED = "Rejected"
    WITHDRAWN = "Withdrawn"
    ACCEPTED = "Accepted"
    CLOSED = "Closed"


class EventType(StrEnum):
    APPLICATION = "application"
    REJECTION = "rejection"
    ASSESSMENT = "assessment"
    INTERVIEW = "interview"
    OFFER = "offer"
    OTHER = "other"
    MANUAL = "manual"


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def timestamp(value: str) -> str:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Date/time must include a timezone.")
    return dt.astimezone(UTC).isoformat(timespec="seconds")


class ApplicationInput(BaseModel):
    company: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=300)
    applied_on: str = ""
    requisition_id: str = Field(default="", max_length=200)
    stage: Stage = Stage.APPLIED
    outcome: Outcome = Outcome.ACTIVE
    notes: str = Field(default="", max_length=10000)

    @field_validator("company", "role", "requisition_id", "notes", mode="before")
    @classmethod
    def trim(cls, value: str) -> str:
        return value.strip()

    @field_validator("applied_on")
    @classmethod
    def valid_date(cls, value: str) -> str:
        if value:
            from datetime import date

            return date.fromisoformat(value).isoformat()
        return value


class Extraction(BaseModel):
    company: str | None
    role: str | None
    requisition_id: str | None
    applied_on: str | None
    deadline_at: str | None
    interview_at: str | None
    evidence: str

    @field_validator("company", "role", "requisition_id")
    @classmethod
    def clean_field(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if len(value) > 300:
                raise ValueError("Extracted field too long.")
        return value or None

    @field_validator("company", "requisition_id")
    @classmethod
    def short_field(cls, value: str | None) -> str | None:
        if value and len(value) > 200:
            raise ValueError("Extracted field too long.")
        return value

    @field_validator("applied_on")
    @classmethod
    def check_date(cls, value: str | None) -> str | None:
        if value:
            from datetime import date

            return date.fromisoformat(value).isoformat()
        return None

    @field_validator("deadline_at", "interview_at")
    @classmethod
    def check_timestamp(cls, value: str | None) -> str | None:
        return timestamp(value) if value else None


def project_status(stage: str, outcome: str, event: str) -> tuple[str, str]:
    """Only explicit manual changes reopen terminal applications or regress stages."""
    if outcome != Outcome.ACTIVE:
        return stage, outcome
    if event == EventType.REJECTION:
        return stage, Outcome.REJECTED
    mapping = {
        EventType.APPLICATION: Stage.APPLIED,
        EventType.ASSESSMENT: Stage.ASSESSMENT,
        EventType.INTERVIEW: Stage.INTERVIEW,
        EventType.OFFER: Stage.OFFER,
    }
    candidate = mapping.get(event)
    stages = list(Stage)
    if candidate and stages.index(candidate) > stages.index(Stage(stage)):
        stage = candidate
    return str(stage), str(outcome)
