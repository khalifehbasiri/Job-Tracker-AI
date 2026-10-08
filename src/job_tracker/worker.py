"""Resumable mailbox imports, bounded spending, and conservative matching."""

import json
import math
from datetime import UTC, datetime, timedelta
from threading import Event

import httpx
from sqlalchemy import func, select

from job_tracker.ai import RATES, Analyzer, estimated_cost
from job_tracker.db import Account, Application, ApplicationEvent, Job, Message, Review, Scan, Usage
from job_tracker.domain import ApplicationInput, now, timestamp
from job_tracker.email import Mailbox
from job_tracker.errors import ReviewRequired, UserFacingError, blocks_scan, describe_error
from job_tracker.services import Tracker, record


class BudgetReached(Exception):
    pass


def match_application(session, message: Message, extraction: dict, search_id: int):
    """Exact thread/ID matches cross years; weaker company/role matches stay search-scoped."""
    if message.thread_id:
        ids = list(
            session.scalars(
                select(ApplicationEvent.application_id)
                .join(Message)
                .where(
                    Message.account_id == message.account_id, Message.thread_id == message.thread_id
                )
            ).unique()
        )
        if len(ids) == 1:
            app = session.get(Application, ids[0])
            extracted_id = extraction.get("requisition_id") or ""
            if (
                app.requisition_id
                and extracted_id
                and app.requisition_id.casefold() != extracted_id.casefold()
            ):
                return None, "The requisition ID conflicts with the email thread."
            return app, ""
        if len(ids) > 1:
            return None, "This email thread contains multiple applications."
    company = (extraction.get("company") or "").casefold()
    role = (extraction.get("role") or "").casefold()
    requisition = (extraction.get("requisition_id") or "").casefold()
    apps = list(session.scalars(select(Application)))
    if company and requisition:
        matches = [
            app
            for app in apps
            if app.company.casefold() == company and app.requisition_id.casefold() == requisition
        ]
        if len(matches) == 1:
            return matches[0], ""
        if len(matches) > 1:
            return None, "Multiple applications share this requisition ID."
    matches = [
        app
        for app in apps
        if app.search_id == search_id
        and company
        and role
        and app.company.casefold() == company
        and app.role.casefold() == role
    ]
    if len(matches) == 1:
        if (
            requisition
            and matches[0].requisition_id
            and (matches[0].requisition_id.casefold() != requisition)
        ):
            return None, "The requisition ID conflicts with the matching company and role."
        return matches[0], ""
    return None, "Multiple roles match this email." if matches else "No exact application match."


class Importer:
    def __init__(self, tracker: Tracker, vault, analyzer_factory=Analyzer, mailbox_factory=Mailbox):
        self.tracker, self.vault = tracker, vault
        self.analyzer_factory, self.mailbox_factory = analyzer_factory, mailbox_factory
        self.cancelled = Event()

    def preview(self, start: str, end: str, provider: str = "all") -> dict:
        if provider not in ("all", "gmail", "outlook"):
            raise ValueError("Choose Gmail, Outlook, or all mailboxes.")
        if self.cancelled.is_set():
            raise BudgetReached("Scan paused. Preview the range again to continue.")
        start, end = timestamp(start), timestamp(end)
        if start >= end:
            raise ValueError("Choose an end date after the start date.")
        accounts = [
            account
            for account in self.tracker.accounts()
            if (provider == "all" or account["provider"] == provider)
            and account["credential_ref"]
            and self.vault.get(account["credential_ref"])
        ]
        if not accounts:
            name = "a mailbox" if provider == "all" else provider.title()
            raise UserFacingError(f"Connect {name} in Settings first.")
        candidates, dates, uncached, total = {}, {}, 0, 0
        for account in accounts:
            mailbox = self.mailbox_factory(account, self.vault)
            ids = mailbox.list_ids(start, end, self.cancelled.is_set)
            if self.cancelled.is_set():
                raise BudgetReached("Scan paused. Preview the range again to continue.")
            candidates[str(account["id"])] = ids
            dates[str(account["id"])] = getattr(mailbox, "received_dates", {})
            total += len(ids)
            with self.tracker.db.sessions() as session:
                known = set()
                for row in session.scalars(
                    select(Message).where(
                        Message.account_id == account["id"], Message.result_json != ""
                    )
                ):
                    cached = json.loads(row.result_json)
                    if cached.get("probability", 1) < 0.1 or "extraction" in cached:
                        known.add(row.provider_id)
            uncached += sum(provider_id not in known for provider_id in ids)
        return {
            "start": start,
            "end": end,
            "candidates": candidates,
            "dates": dates,
            "total": total,
            "estimate": estimated_cost(uncached),
            "provider": provider,
        }

    def create_scan(self, search_id: int, plan: dict, budget: float) -> int:
        if not math.isfinite(budget) or budget <= 0 or budget > 10000:
            raise ValueError("Enter a spending limit greater than $0 and at most $10,000 USD.")
        with self.tracker.db.sessions.begin() as session:
            scan = Scan(
                search_id=search_id, start_at=plan["start"], end_at=plan["end"], budget=budget
            )
            session.add(scan)
            session.flush()
            return scan.id

    def bill(self, scan_id: int, message_id: int, operation: str, model, amount):
        with self.tracker.db.sessions.begin() as session:
            scan = session.get(Scan, scan_id)
            if operation == "settle":
                usage = session.get(Usage, model)
                input_tokens, output_tokens = amount["input_tokens"], amount.get("output_tokens", 0)
                rates = RATES[usage.operation]
                cost = (input_tokens * rates[0] + output_tokens * rates[1]) / 1_000_000
                scan.spent += cost - usage.cost
                usage.input_tokens, usage.output_tokens, usage.cost = (
                    input_tokens,
                    output_tokens,
                    cost,
                )
                return
            if self.cancelled.is_set():
                raise BudgetReached("Scan paused.")
            if scan.spent + amount > scan.budget:
                raise BudgetReached("Spending limit reached. Increase the limit to resume.")
            usage = Usage(
                scan_id=scan_id,
                message_id=message_id,
                operation=operation,
                model=model,
                input_tokens=0,
                output_tokens=0,
                cost=amount,
            )
            scan.spent += amount
            session.add(usage)
            session.flush()
            return usage.id

    def stage_message(
        self, account: dict, provider_id: str, scan_id: int, search_id: int, received_at=""
    ) -> int:
        with self.tracker.db.sessions.begin() as session:
            message = session.scalar(
                select(Message).where(
                    Message.account_id == account["id"], Message.provider_id == provider_id
                )
            )
            if message is None:
                # Persist message identity before downloading: failures stay resumable.
                message = Message(
                    account_id=account["id"],
                    provider_id=provider_id,
                    sender="",
                    subject="",
                    body="",
                    received_at=received_at,
                    state="fetch_pending",
                )
                session.add(message)
                session.flush()
            message_id = message.id
            if not message.received_at and received_at:
                message.received_at = received_at
        with self.tracker.db.sessions.begin() as session:
            job = session.scalar(
                select(Job).where(Job.message_id == message_id, Job.search_id == search_id)
            )
            if job is None:
                job = Job(message_id=message_id, search_id=search_id, scan_id=scan_id)
                session.add(job)
            elif job.state in ("pending", "error"):
                job.scan_id = scan_id
            session.flush()
            return job.id

    def process(self, job_id: int, analyzer):
        with self.tracker.db.sessions.begin() as session:
            job = session.get(Job, job_id)
            if job.state in ("done", "review", "unavailable") or job.attempts >= 3:
                return
            if job.retry_at and job.retry_at > now():
                return
            job.attempts += 1
            message = session.get(Message, job.message_id)
            result = json.loads(message.result_json or "{}")
            account = record(session.get(Account, message.account_id))

        if result.get("review_reason"):
            self.require_review(job_id, result, result["review_reason"])
            return
        if (
            job.error
            == "The record or provider response could not be validated. Check setup or retry."
            and result.get("kind")
        ):
            self.require_review(
                job_id,
                result,
                "The previous AI extraction could not be validated. "
                "Review manually without another API charge.",
            )
            return

        if message.state == "fetch_pending":
            try:
                mail = self.mailbox_factory(account, self.vault).get(message.provider_id)
            except httpx.HTTPStatusError as error:
                if error.response.status_code != 404:
                    raise
                with self.tracker.db.sessions.begin() as session:
                    session.get(Job, job_id).state = "unavailable"
                    session.get(Job, job_id).error = describe_error(error)
                    session.get(Message, message.id).state = "unavailable"
                return
            with self.tracker.db.sessions.begin() as session:
                message = session.get(Message, message.id)
                for key, value in vars(mail).items():
                    setattr(message, key, value)
                message.state = "pending"

        if not message.body.strip():
            self.require_review(
                job_id, result, "This email has no readable body. Review it manually."
            )
            return

        def bill(operation, model, amount):
            return self.bill(job.scan_id, message.id, operation, model, amount)

        if "kind" not in result:
            result = analyzer.classify(message, bill)
            with self.tracker.db.sessions.begin() as session:
                session.get(Message, message.id).result_json = json.dumps(result)
        if result["probability"] >= 0.1 and "extraction" not in result:
            result["extraction"] = analyzer.extract(message, bill)
            with self.tracker.db.sessions.begin() as session:
                session.get(Message, message.id).result_json = json.dumps(result)
        with self.tracker.db.sessions.begin() as session:
            job = session.get(Job, job_id)
            if result["probability"] < 0.1:
                job.state = "done"
                session.get(Message, message.id).state = "ignored"
                return
            extraction = result["extraction"]
            app, reason = match_application(session, message, extraction, job.search_id)
            confident = result["probability"] >= 0.9 and result["confidence"] >= 0.9
            if (
                not app
                and confident
                and result["kind"] == "application"
                and extraction.get("company")
                and extraction.get("role")
                and reason == "No exact application match."
            ):
                data = ApplicationInput(
                    company=extraction["company"],
                    role=extraction["role"],
                    requisition_id=extraction.get("requisition_id") or "",
                    applied_on=extraction.get("applied_on") or "",
                )
                app = Application(
                    search_id=job.search_id,
                    **data.model_dump(mode="json"),
                    status_at=message.received_at,
                )
                session.add(app)
                session.flush()
            if app and confident and result["kind"] != "other":
                self.tracker.add_event(session, app, message, result)
                job.state = "done"
            else:
                session.add(
                    Review(
                        job_id=job.id,
                        search_id=job.search_id,
                        proposed_json=json.dumps(result),
                        reason=reason or "The classification needs your confirmation.",
                    )
                )
                job.state = "review"
            session.get(Message, message.id).state = "processed"

    def require_review(self, job_id, result, reason, extraction=None):
        result = {"probability": 0.5, "confidence": 0, "kind": "other"} | result
        result["review_reason"] = reason
        result["extraction"] = (
            extraction
            or result.get("extraction")
            or {
                key: None
                for key in (
                    "company",
                    "role",
                    "requisition_id",
                    "applied_on",
                    "deadline_at",
                    "interview_at",
                )
            }
            | {"evidence": ""}
        )
        with self.tracker.db.sessions.begin() as session:
            job = session.get(Job, job_id)
            message = session.get(Message, job.message_id)
            message.result_json = json.dumps(result)
            message.state = "processed"
            if session.scalar(select(Review.id).where(Review.job_id == job_id)) is None:
                session.add(
                    Review(
                        job_id=job_id,
                        search_id=job.search_id,
                        proposed_json=json.dumps(result),
                        reason=reason,
                    )
                )
            job.state, job.error, job.retry_at = "review", "", ""

    def run(self, scan_id: int, plan: dict | None = None, progress=lambda _text: None):
        with self.tracker.db.sessions.begin() as session:
            scan = session.get(Scan, scan_id)
            scan.state = "running"
            scan.error = ""
        analyzer = None
        try:
            if self.cancelled.is_set():
                raise BudgetReached("Scan paused; resume to continue.")
            analyzer = self.analyzer_factory(self.vault.get("openai"))
            plan = plan or self.preview(scan.start_at, scan.end_at)
            accounts = {row["id"]: row for row in self.tracker.accounts()}
            staged = []
            for account_id, ids in plan["candidates"].items():
                for index, provider_id in enumerate(ids):
                    if self.cancelled.is_set():
                        raise BudgetReached("Scan paused; resume to continue.")
                    progress(f"Queuing email {index + 1} of {len(ids)}…")
                    staged.append(
                        self.stage_message(
                            accounts[int(account_id)],
                            provider_id,
                            scan_id,
                            scan.search_id,
                            plan.get("dates", {}).get(account_id, {}).get(provider_id, ""),
                        )
                    )
            # Sort across all mailboxes using actual dates, including durable resumed jobs.
            with self.tracker.db.sessions() as session:
                unfinished = session.scalars(
                    select(Job.id).where(
                        Job.scan_id == scan_id, Job.state.in_(["pending", "error"])
                    )
                )
                staged = list(dict.fromkeys([*staged, *unfinished]))
            dated = []
            for index, job_id in enumerate(staged):
                if self.cancelled.is_set():
                    raise BudgetReached("Scan paused; resume to continue.")
                with self.tracker.db.sessions() as session:
                    job = session.get(Job, job_id)
                    message = session.get(Message, job.message_id)
                if job.state in ("done", "review", "unavailable"):
                    continue
                if not message.received_at:
                    progress(f"Reading email dates {index + 1} of {len(staged)}…")
                    mailbox = self.mailbox_factory(accounts[message.account_id], self.vault)
                    try:
                        received = mailbox.received_at(message.provider_id)
                    except httpx.HTTPStatusError as error:
                        if error.response.status_code != 404:
                            raise
                        with self.tracker.db.sessions.begin() as session:
                            session.get(Job, job_id).state = "unavailable"
                            session.get(Message, message.id).state = "unavailable"
                        continue
                    with self.tracker.db.sessions.begin() as session:
                        session.get(Message, message.id).received_at = timestamp(received)
                    message.received_at = timestamp(received)
                dated.append((message.received_at, message.state == "fetch_pending", job_id))
            staged = [row[2] for row in sorted(dated)]
            # Every identity is durable. Only a fully resolved queue advances sync checkpoints.
            for index, job_id in enumerate(staged):
                if self.cancelled.is_set():
                    raise BudgetReached("Scan paused; resume to continue.")
                progress(f"Processing email {index + 1} of {len(staged)}…")
                try:
                    self.process(job_id, analyzer)
                except ReviewRequired as error:
                    with self.tracker.db.sessions() as session:
                        job = session.get(Job, job_id)
                        result = json.loads(
                            session.get(Message, job.message_id).result_json or "{}"
                        )
                    self.require_review(job_id, result, str(error), error.extraction)
                except BudgetReached:
                    with self.tracker.db.sessions.begin() as session:
                        session.get(Job, job_id).attempts -= 1
                    raise
                except Exception as error:
                    # Provider exception strings can contain email content or credentials.
                    with self.tracker.db.sessions.begin() as session:
                        job = session.get(Job, job_id)
                        job.state = "error"
                        job.error = describe_error(error)
                        session.get(Scan, scan_id).error = job.error
                        job.retry_at = (datetime.now(UTC) + timedelta(minutes=1)).isoformat(
                            timespec="seconds"
                        )
                    if blocks_scan(error):
                        break
            with self.tracker.db.sessions.begin() as session:
                pending = session.scalar(
                    select(Job.id).where(
                        Job.scan_id == scan_id, Job.state.in_(["pending", "error"])
                    )
                )
                session.get(Scan, scan_id).state = "paused" if pending else "completed"
                if not pending:
                    session.get(Scan, scan_id).error = ""
        except BudgetReached as error:
            with self.tracker.db.sessions.begin() as session:
                session.get(Scan, scan_id).state = "paused"
                session.get(Scan, scan_id).error = str(error)
        except Exception as error:
            with self.tracker.db.sessions.begin() as session:
                session.get(Scan, scan_id).state = "paused"
                session.get(Scan, scan_id).error = describe_error(error)
            raise
        finally:
            if analyzer:
                analyzer.close()
        with self.tracker.db.sessions() as session:
            return record(session.get(Scan, scan_id))

    def scans(self, search_id: int) -> list[dict]:
        with self.tracker.db.sessions() as session:
            rows = list(
                session.scalars(
                    select(Scan)
                    .where(Scan.search_id == search_id)
                    .order_by(Scan.id.desc())
                    .limit(20)
                )
            )
            output = []
            for row in rows:
                counts = dict(
                    session.execute(
                        select(Job.state, func.count(Job.id))
                        .where(Job.scan_id == row.id)
                        .group_by(Job.state)
                    ).all()
                )
                output.append(
                    record(row)
                    | {
                        "processed": counts.get("done", 0),
                        "review_count": counts.get("review", 0),
                        "failed": counts.get("error", 0),
                        "pending": counts.get("pending", 0),
                        "unavailable": counts.get("unavailable", 0),
                    }
                )
            return output

    def resume(self, scan_id: int, budget: float):
        if not math.isfinite(budget) or budget <= 0:
            raise ValueError("Enter a positive budget.")
        with self.tracker.db.sessions.begin() as session:
            scan = session.get(Scan, scan_id)
            if budget < scan.spent:
                raise ValueError("Budget cannot be below already recorded usage.")
            scan.budget = budget
            for job in session.scalars(
                select(Job).where(Job.scan_id == scan_id, Job.state == "error")
            ):
                job.attempts, job.retry_at = 0, ""
        return self.run(scan_id)
