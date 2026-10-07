"""Application workflows shared by the desktop and background worker."""

import json
import sqlite3
from datetime import date
from pathlib import Path

from sqlalchemy import select

from job_tracker.db import (
    Account,
    Application,
    ApplicationEvent,
    Database,
    Job,
    Message,
    Review,
    Search,
    Setting,
    Task,
)
from job_tracker.domain import ApplicationInput, EventType, now, project_status, timestamp


def record(row) -> dict:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


class Tracker:
    def __init__(self, db: Database):
        self.db = db

    def searches(self) -> list[dict]:
        with self.db.sessions() as session:
            return [
                record(row) for row in session.scalars(select(Search).order_by(Search.id.desc()))
            ]

    def create_search(self, name: str, start: str = "", end: str = "") -> int:
        name = name.strip()
        if not name or len(name) > 200:
            raise ValueError("Enter a search name of 1–200 characters.")
        for value in (start, end):
            if value:
                date.fromisoformat(value)
        if start and end and start > end:
            raise ValueError("The end date must follow the start date.")
        with self.db.sessions.begin() as session:
            row = Search(name=name, start_date=start, end_date=end)
            session.add(row)
            session.flush()
            return row.id

    def archive_search(self, search_id: int, archived: bool):
        with self.db.sessions.begin() as session:
            row = session.get(Search, search_id)
            if row is None:
                raise ValueError("Search no longer exists.")
            row.archived = archived

    def applications(self, search_id: int) -> list[dict]:
        with self.db.sessions() as session:
            query = select(Application).where(Application.search_id == search_id)
            return [
                record(row)
                for row in session.scalars(query.order_by(Application.updated_at.desc()))
            ]

    def save_application(self, search_id: int, data: dict, application_id: int = 0) -> int:
        values = ApplicationInput.model_validate(data).model_dump(mode="json")
        with self.db.sessions.begin() as session:
            if session.get(Search, search_id) is None:
                raise ValueError("Select a job search first.")
            if application_id:
                row = session.get(Application, application_id)
                if row is None or row.search_id != search_id:
                    raise ValueError("Application does not belong to this search.")
                status_changed = (row.stage, row.outcome) != (values["stage"], values["outcome"])
                if status_changed:
                    row.manual_override = True
                    row.status_at = now()
                for key, value in values.items():
                    setattr(row, key, value)
                row.updated_at = now()
                kind, evidence = "manual", "Record edited manually."
            else:
                row = Application(search_id=search_id, **values)
                session.add(row)
                session.flush()
                kind, evidence = "manual", "Record added manually."
            session.add(
                ApplicationEvent(
                    application_id=row.id, kind=kind, evidence=evidence, effective_at=now()
                )
            )
            return row.id

    def move_application(self, application_id: int, destination: int):
        with self.db.sessions.begin() as session:
            row = session.get(Application, application_id)
            if row is None or session.get(Search, destination) is None:
                raise ValueError("Application or destination search does not exist.")
            row.search_id = destination
            row.updated_at = now()

    def events(self, application_id: int) -> list[dict]:
        with self.db.sessions() as session:
            query = select(ApplicationEvent).where(
                ApplicationEvent.application_id == application_id
            )
            return [
                record(row)
                for row in session.scalars(query.order_by(ApplicationEvent.effective_at.desc()))
            ]

    def tasks(self, search_id: int) -> list[dict]:
        with self.db.sessions() as session:
            rows = session.execute(
                select(Task, Application)
                .join(Application)
                .where(Application.search_id == search_id)
                .order_by(Task.due_at)
            )
            return [record(task) | {"company": app.company, "role": app.role} for task, app in rows]

    def complete_task(self, task_id: int, completed: bool):
        with self.db.sessions.begin() as session:
            row = session.get(Task, task_id)
            if row is None:
                raise ValueError("Task no longer exists.")
            row.completed = completed

    def reviews(self, search_id: int) -> list[dict]:
        with self.db.sessions() as session:
            rows = session.execute(
                select(Review, Message)
                .join(Job, Review.job_id == Job.id)
                .join(Message, Job.message_id == Message.id)
                .where(Review.search_id == search_id, Review.state == "pending")
            )
            return [
                record(review)
                | {
                    "subject": message.subject,
                    "sender": message.sender,
                    "body": message.body,
                    "message_id": message.id,
                    "received_at": message.received_at,
                }
                for review, message in rows
            ]

    def accounts(self) -> list[dict]:
        with self.db.sessions() as session:
            return [record(row) for row in session.scalars(select(Account))]

    def get_setting(self, key: str, default: str = "") -> str:
        with self.db.sessions() as session:
            row = session.get(Setting, key)
            return row.value if row else default

    def set_setting(self, key: str, value: str):
        allowed = {
            "extraction_model",
            "poll_minutes",
            "ai_enabled",
            "sync_budget",
            "selected_search",
            "daily_budget",
        }
        if key not in allowed:
            raise ValueError("This setting cannot be stored in the database.")
        with self.db.sessions.begin() as session:
            session.merge(Setting(key=key, value=value))

    def backup(self, destination: Path):
        if destination.resolve() == self.db.path.resolve():
            raise ValueError("Choose a different file for the backup.")
        with sqlite3.connect(self.db.path) as source, sqlite3.connect(destination) as target:
            source.backup(target)

    def add_event(self, session, app: Application, message: Message, result: dict):
        kind = EventType(result["kind"])
        existing = session.scalar(
            select(ApplicationEvent).where(
                ApplicationEvent.application_id == app.id,
                ApplicationEvent.message_id == message.id,
                ApplicationEvent.kind == kind,
            )
        )
        if existing:
            return
        effective_at = timestamp(message.received_at)
        extraction = result.get("extraction", {})
        event = ApplicationEvent(
            application_id=app.id,
            message_id=message.id,
            kind=kind,
            evidence=extraction.get("evidence", ""),
            effective_at=effective_at,
        )
        session.add(event)
        session.flush()
        if not app.manual_override and effective_at >= app.status_at:
            app.stage, app.outcome = project_status(app.stage, app.outcome, kind)
            app.status_at = effective_at
        app.updated_at = now()
        deadline_title = (
            "Assessment deadline" if kind == EventType.ASSESSMENT else "Application deadline"
        )
        for field, title in (("deadline_at", deadline_title), ("interview_at", "Interview")):
            if extraction.get(field):
                due_at = timestamp(extraction[field])
                if session.scalar(
                    select(Task.id).where(
                        Task.application_id == app.id, Task.title == title, Task.due_at == due_at
                    )
                ):
                    continue  # Reminder emails should not recreate a task already completed.
                session.add(
                    Task(
                        application_id=app.id,
                        event_id=event.id,
                        title=title,
                        due_at=due_at,
                    )
                )

    def resolve_review(self, review_id: int, application_id: int = 0, ignore: bool = False):
        with self.db.sessions.begin() as session:
            review = session.get(Review, review_id)
            if review is None or review.state != "pending":
                raise ValueError("This review has already been resolved.")
            job = session.get(Job, review.job_id)
            message = session.get(Message, job.message_id)
            if ignore:
                review.state, job.state = "ignored", "done"
                return
            result = json.loads(review.proposed_json)
            values = result.get("extraction", {})
            if application_id:
                app = session.get(Application, application_id)
                if app is None:
                    raise ValueError("Select an existing application.")
            else:
                data = ApplicationInput(
                    company=values.get("company") or "",
                    role=values.get("role") or "",
                    requisition_id=values.get("requisition_id") or "",
                    applied_on=values.get("applied_on") or "",
                )
                app = Application(
                    search_id=review.search_id,
                    **data.model_dump(mode="json"),
                    status_at=message.received_at,
                )
                session.add(app)
                session.flush()
            self.add_event(session, app, message, result)
            review.state, job.state = "accepted", "done"
