"""Expose application services to QML without putting business rules in the UI."""

import calendar
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from time import monotonic

from PySide6.QtCore import Property, QObject, QRunnable, Qt, QThreadPool, QTimer, QUrl, Signal, Slot
from PySide6.QtWidgets import QFileDialog
from sqlalchemy import select

from job_tracker.ai import Analyzer
from job_tracker.credentials import Credentials
from job_tracker.db import Account, Search, Usage
from job_tracker.email import connect_gmail, connect_outlook
from job_tracker.errors import describe_error
from job_tracker.excel import export_search, import_rows, preview_import
from job_tracker.oauth import HOMEPAGE, PRIVACY_URL, google_desktop_client
from job_tracker.services import Tracker
from job_tracker.worker import BudgetReached, Importer


class Signals(QObject):
    success = Signal(object)
    failed = Signal(str)
    progress = Signal(str)


class Work(QRunnable):
    def __init__(self, action):
        super().__init__()
        self.action = action
        self.signals = Signals()
        self._last_progress = float("-inf")

    def report_progress(self, text):
        # Bound the event queue independently of mailbox size or staging speed.
        current = monotonic()
        if current - self._last_progress >= 0.1:
            self._last_progress = current
            self.signals.progress.emit(text)

    def run(self):
        try:
            self.signals.success.emit(self.action())
        except BudgetReached as error:
            self.signals.failed.emit(str(error))
        except Exception as error:
            self.signals.failed.emit(describe_error(error))


class Bridge(QObject):
    changed = Signal()
    messageChanged = Signal()
    searchesChanged = Signal()
    applicationsChanged = Signal()
    tasksChanged = Signal()
    reviewsChanged = Signal()
    scansChanged = Signal()
    accountsChanged = Signal()
    eventsChanged = Signal()
    configurationChanged = Signal()
    importReady = Signal()
    scanReady = Signal()

    def __init__(self, tracker: Tracker, vault: Credentials, parent=None, onboarding=True):
        super().__init__(parent)
        self.tracker, self.vault = tracker, vault
        self.importer = Importer(tracker, vault)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        # A serialized import prevents concurrent billing. Reads have their own
        # pool so the dashboard can refresh during a long network operation.
        self.read_pool = QThreadPool(self)
        self.read_pool.setMaxThreadCount(1)
        self._read_jobs = set()
        self._refreshing = False
        self._full_refresh_pending = False
        self._revision = 0
        self._closing = False
        self._settings = {}
        self._api_ready = self._google_configured = False
        self._searches, self._apps, self._tasks = [], [], []
        self._reviews, self._scans, self._accounts = [], [], []
        self._event_request = 0
        self._busy = False
        self._operation = ""
        self._mailbox_messages = {}
        self._message = "Your records stay on this computer. AI is optional."
        self._search_id = int(tracker.get_setting("selected_search", "0"))
        self._events, self._import_preview, self._scan_plan = [], {}, {}
        self._import_path = ""
        self._estimate = {}
        self._tray = False
        self._work = None
        self._setup_needed = (
            onboarding
            and tracker.get_setting("setup_complete", "true" if tracker.searches() else "false")
            != "true"
        )
        self._provider = tracker.get_setting("selected_provider", "gmail")
        if self._provider not in ("gmail", "outlook", "all"):
            self._provider = "gmail"
        if not tracker.searches():
            self._search_id = tracker.create_search("My job search")
            tracker.set_setting("setup_complete", "false")
        self.refresh()
        self.timer = QTimer(self)
        self.timer.setInterval(300000)
        self.timer.timeout.connect(self.poll)
        self.timer.start()
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(2000)
        self.refresh_timer.timeout.connect(self.refreshWhileBusy)
        self.refresh_timer.start()

    def refreshWhileBusy(self):
        if self._busy:
            self.requestRefresh()

    def readSnapshot(self, search_id, credentials=False, connected=None):
        searches = self.tracker.searches()
        if search_id not in [item["id"] for item in searches]:
            search_id = searches[0]["id"]
        accounts = self.tracker.accounts()
        connected = connected or {}
        snapshot = {
            "search_id": search_id,
            "searches": searches,
            "apps": self.tracker.applications(search_id),
            "tasks": self.tracker.tasks(search_id),
            "reviews": self.tracker.reviews(search_id),
            "scans": self.importer.scans(search_id),
            "accounts": [
                {
                    **item,
                    "connected": bool(self.vault.get(item["credential_ref"]))
                    if credentials
                    else connected.get(item["id"], False),
                }
                for item in accounts
            ],
            "settings": self.tracker.settings(),
        }
        if credentials:
            snapshot["api_ready"] = bool(self.vault.get("openai"))
            snapshot["google_configured"] = bool(self.vault.get("google-oauth-client"))
        return snapshot

    def applySnapshot(self, snapshot):
        selected = self._search_id
        accounts_changed = self._accounts != snapshot["accounts"]
        self._search_id = snapshot["search_id"]
        for name, signal in (
            ("searches", self.searchesChanged),
            ("apps", self.applicationsChanged),
            ("tasks", self.tasksChanged),
            ("reviews", self.reviewsChanged),
            ("scans", self.scansChanged),
            ("accounts", self.accountsChanged),
        ):
            if getattr(self, "_" + name) != snapshot[name]:
                setattr(self, "_" + name, snapshot[name])
                signal.emit()
        configuration = (self._settings, self._api_ready, self._google_configured)
        self._settings = snapshot["settings"]
        self._api_ready = snapshot.get("api_ready", self._api_ready)
        self._google_configured = snapshot.get("google_configured", self._google_configured)
        if configuration != (self._settings, self._api_ready, self._google_configured):
            self.configurationChanged.emit()
        if selected != self._search_id or accounts_changed:
            # Connection status text also depends on the mailbox model.
            self.changed.emit()

    def readBackground(self, action, complete, failed=None):
        work = Work(action)
        self._read_jobs.add(work)

        def finish(result):
            self._read_jobs.discard(work)
            if not self._closing:
                complete(result)

        def failure(text):
            self._read_jobs.discard(work)
            if not self._closing and failed:
                failed(text)

        work.signals.success.connect(finish, Qt.QueuedConnection)
        work.signals.failed.connect(failure, Qt.QueuedConnection)
        self.read_pool.start(work)

    def requestRefresh(self, credentials=False):
        if self._closing:
            return
        if self._refreshing:
            self._full_refresh_pending |= credentials
            return
        self._refreshing = True
        search_id, revision = self._search_id, self._revision
        connected = {item["id"]: item["connected"] for item in self._accounts}

        def finish(snapshot=None):
            self._refreshing = False
            if snapshot and revision == self._revision:
                self.applySnapshot(snapshot)
            elif snapshot and credentials:
                # A theme/local edit invalidated this read. Do not lose a newly
                # connected mailbox or key while discarding its stale settings.
                self._full_refresh_pending = True
            if self._full_refresh_pending:
                self._full_refresh_pending = False
                self.requestRefresh(credentials=True)

        self.readBackground(
            lambda: self.readSnapshot(search_id, credentials, connected),
            finish,
            lambda _text: finish(),
        )

    def refresh(self):
        if self._busy:
            self.requestRefresh()
            return
        # Initial load and small, idle local edits. Never called synchronously
        # from import progress, the refresh timer or background completion.
        self._revision += 1
        self.applySnapshot(self.readSnapshot(self._search_id, credentials=True))
        self.changed.emit()

    searches = Property("QVariantList", lambda self: self._searches, notify=searchesChanged)
    applications = Property("QVariantList", lambda self: self._apps, notify=applicationsChanged)
    tasks = Property("QVariantList", lambda self: self._tasks, notify=tasksChanged)
    reviews = Property("QVariantList", lambda self: self._reviews, notify=reviewsChanged)
    scans = Property("QVariantList", lambda self: self._scans, notify=scansChanged)
    accounts = Property("QVariantList", lambda self: self._accounts, notify=accountsChanged)
    events = Property("QVariantList", lambda self: self._events, notify=eventsChanged)
    selectedSearch = Property(int, lambda self: self._search_id, notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    scanActive = Property(
        bool, lambda self: self._busy and self._operation == "scan", notify=changed
    )
    message = Property(str, lambda self: self._message, notify=messageChanged)
    apiReady = Property(bool, lambda self: self._api_ready, notify=configurationChanged)
    aiEnabled = Property(
        bool, lambda self: self._settings.get("ai_enabled") == "true", notify=configurationChanged
    )
    syncBudget = Property(
        str, lambda self: self._settings.get("sync_budget", "0.25"), notify=configurationChanged
    )
    dailyBudget = Property(
        str, lambda self: self._settings.get("daily_budget", "1.00"), notify=configurationChanged
    )
    estimate = Property("QVariantMap", lambda self: self._estimate, notify=changed)
    importPreview = Property(
        "QVariantMap",
        lambda self: {
            key: self._import_preview.get(key, [] if key != "count" else 0)
            for key in ("headers", "samples", "count")
        },
        notify=changed,
    )
    trayAvailable = Property(bool, lambda self: self._tray, notify=changed)
    dataPath = Property(str, lambda self: str(self.tracker.db.path), constant=True)
    privacyUrl = Property(str, lambda self: PRIVACY_URL, constant=True)
    setupGuideUrl = Property(
        str, lambda self: HOMEPAGE + "/blob/main/docs/mailbox-setup.md", constant=True
    )
    setupNeeded = Property(bool, lambda self: self._setup_needed, notify=changed)
    selectedProvider = Property(str, lambda self: self._provider, notify=changed)
    darkMode = Property(
        bool,
        lambda self: self._settings.get("theme", "light") == "dark",
        notify=configurationChanged,
    )
    googleConfigured = Property(
        bool,
        lambda self: self._google_configured,
        notify=configurationChanged,
    )
    microsoftClient = Property(
        str,
        lambda self: self._settings.get("microsoft_client_id", ""),
        notify=configurationChanged,
    )
    connectingProvider = Property(
        str,
        lambda self: (
            self._operation.removeprefix("oauth:") if self._operation.startswith("oauth:") else ""
        ),
        notify=changed,
    )
    mailboxStatuses = Property(
        "QVariantMap",
        lambda self: {provider: self.mailboxStatus(provider) for provider in ("gmail", "outlook")},
        notify=changed,
    )

    @Slot(str)
    def selectProvider(self, provider):
        if self._busy or provider not in ("gmail", "outlook", "all"):
            return
        self._provider = provider
        self._scan_plan, self._estimate = {}, {}
        self.tracker.set_setting("selected_provider", provider)
        self.changed.emit()

    @Slot()
    def finishSetup(self):
        self._setup_needed = False
        self.tracker.set_setting("setup_complete", "true")
        self.changed.emit()

    @Slot(str, result=bool)
    def nameInitialSearch(self, name):
        def save():
            value = name.strip()
            if not value or len(value) > 200:
                raise ValueError("Enter a search name.")
            with self.tracker.db.sessions.begin() as session:
                session.get(Search, self._search_id).name = value

        return bool(self.local(save))

    @Slot()
    def openSetupGuide(self):
        from PySide6.QtGui import QDesktopServices

        guide = Path(__file__).parents[1] / "help" / "setup.html"
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(guide)))

    @Slot(str, result=str)
    def mailboxStatus(self, provider):
        if provider in self._mailbox_messages:
            return self._mailbox_messages[provider]
        connected = sum(row["provider"] == provider and row["connected"] for row in self._accounts)
        name = "Gmail" if provider == "gmail" else "Outlook"
        return f"{name}: {connected} connected." if connected else f"{name}: no connected mailbox."

    @Slot(str)
    def feedback(self, text):
        self._message = text
        self.messageChanged.emit()

    def local(self, action):
        if self._busy:
            return
        try:
            action()
            self.refresh()
            return True
        except ValueError:
            self.feedback(
                "Check the required fields, date format (YYYY-MM-DD), and selected record."
            )
        except Exception:
            self.feedback("Could not save the change. Your existing records are preserved.")

    def background(self, action, complete=lambda _result: None, operation="", on_failure=None):
        if self._busy:
            self.feedback("Wait for the current operation, or pause the scan first.")
            return
        # Reset on the UI thread before dispatch, so Pause/Quit cannot be lost between
        # mailbox enumeration and AI processing inside the same background operation.
        self.importer.cancelled.clear()
        self._busy = True
        self._operation = operation
        self.changed.emit()
        work = Work(action)
        self._work = work
        work.signals.progress.connect(self.feedback, Qt.QueuedConnection)

        def finished(result):
            if self._closing:
                return
            self._busy = False
            self._operation = ""
            complete(result)
            self.changed.emit()
            self.requestRefresh(credentials=True)

        def failed(text):
            if self._closing:
                return
            self._busy = False
            self._operation = ""
            self.feedback(text)
            if on_failure:
                on_failure(text)
            self.changed.emit()
            self.requestRefresh(credentials=True)

        work.signals.success.connect(finished)
        work.signals.failed.connect(failed)
        self.pool.start(work)

    @Slot(int)
    def selectSearch(self, search_id):
        if self._busy:
            return
        self._search_id = search_id
        self.tracker.set_setting("selected_search", str(search_id))
        self.refresh()

    @Slot(str, str, str)
    def createSearch(self, name, start, end):
        def action():
            self._search_id = self.tracker.create_search(name, start, end)
            self.tracker.set_setting("selected_search", str(self._search_id))
            self.feedback("Job search created.")

        self.local(action)

    @Slot(bool)
    def archiveSearch(self, archived):
        self.local(lambda: self.tracker.archive_search(self._search_id, archived))

    @Slot(str, str, str, bool, result=bool)
    def editSearch(self, name, start, end, archived):
        def save():
            self.tracker.edit_search(self._search_id, name, start, end, archived)
            self.feedback("Job search updated. Records and exports stay with this search.")

        return bool(self.local(save))

    @Slot(bool)
    def setDarkMode(self, enabled):
        theme = "dark" if enabled else "light"
        self._settings = self._settings | {"theme": theme}
        self._revision += 1
        self.configurationChanged.emit()
        self.readBackground(
            lambda: self.tracker.set_setting("theme", theme),
            lambda _: self.requestRefresh(),
            lambda _: self.feedback("Could not save the theme preference."),
        )

    @Slot(str, int)
    def saveApplication(self, data, application_id):
        def action():
            self.tracker.save_application(self._search_id, json.loads(data), application_id)
            self.feedback("Application saved.")

        self.local(action)

    @Slot(int, int)
    def moveApplication(self, application_id, destination):
        self.local(lambda: self.tracker.move_application(application_id, destination))

    @Slot(int)
    def showEvents(self, application_id):
        self._event_request += 1
        request = self._event_request
        self._events = []
        self.eventsChanged.emit()

        def complete(events):
            if request == self._event_request:
                self._events = events
                self.eventsChanged.emit()

        self.readBackground(lambda: self.tracker.events(application_id), complete)

    @Slot(int, bool)
    def completeTask(self, task_id, completed):
        self.local(lambda: self.tracker.complete_task(task_id, completed))

    @Slot(int, int, bool)
    def resolveReview(self, review_id, application_id, ignore):
        self.local(lambda: self.tracker.resolve_review(review_id, application_id, ignore))

    @Slot()
    def exportExcel(self):
        path, _ = QFileDialog.getSaveFileName(
            None, "Export this search", "Job search.xlsx", "Excel workbooks (*.xlsx)"
        )
        if path:
            search_id = self._search_id
            self.background(
                lambda: export_search(self.tracker, search_id, Path(path)),
                lambda _: self.feedback("Excel snapshot exported. No API calls were used."),
            )

    @Slot()
    def previewExcel(self):
        path, _ = QFileDialog.getOpenFileName(
            None, "Import a tracker", "", "Excel workbooks (*.xlsx)"
        )
        if path:
            self._import_path = path

            def complete(preview):
                self._import_preview = preview
                self.importReady.emit()

            self.background(lambda: preview_import(Path(path)), complete)

    @Slot(str)
    def importExcel(self, mapping):
        search_id = self._search_id
        self.background(
            lambda: import_rows(self.tracker, search_id, self._import_preview, json.loads(mapping)),
            lambda result: self.feedback(
                f"Imported {result[0]} records; skipped {result[1]} duplicates."
            ),
        )

    @Slot()
    def backupDatabase(self):
        path, _ = QFileDialog.getSaveFileName(
            None, "Save a database backup", "Job tracker.sqlite3", "SQLite database (*.sqlite3)"
        )
        if path:
            self.background(
                lambda: self.tracker.backup(Path(path)),
                lambda _: self.feedback("Database backup saved. Credentials are excluded."),
            )

    @Slot(str, bool)
    def saveKey(self, value, persist):
        if self._busy:
            return
        if self.local(lambda: self.vault.save("openai", value, persist)):
            self.feedback("API key configured. AI requests use your OpenAI account.")
        else:
            self.feedback(
                "Could not save the key securely. Try Session only if OS storage is unavailable."
            )

    @Slot()
    def removeKey(self):
        self.local(lambda: self.vault.remove("openai"))

    @Slot()
    def testKey(self):
        def test():
            analyzer = Analyzer(self.vault.get("openai"))
            try:
                analyzer.test()
            finally:
                analyzer.close()

        self.background(
            test,
            lambda _: self.feedback(
                "Key accepted; extraction model is accessible. This check did not process email "
                "or verify Decisions access."
            ),
        )

    @Slot(bool, str, str)
    def configureAI(self, enabled, sync_budget, daily_budget):
        def action():
            import math

            for value in (sync_budget, daily_budget):
                if not math.isfinite(float(value)) or not 0 < float(value) <= 10000:
                    raise ValueError("Enter a positive budget.")
            self.tracker.set_setting("ai_enabled", "true" if enabled else "false")
            self.tracker.set_setting("sync_budget", sync_budget)
            self.tracker.set_setting("daily_budget", daily_budget)
            self.feedback("Automatic processing settings saved.")

        self.local(action)

    @Slot(bool)
    def connectGmail(self, persist):
        def connect():
            saved = self.vault.get("google-oauth-client")
            config = json.loads(saved) if saved else None
            if not config:
                from job_tracker.errors import UserFacingError

                raise UserFacingError(
                    "Import your own Google Desktop client JSON in OAuth setup first."
                )
            return connect_gmail(self.tracker, self.vault, config, persist)

        self.connectMailbox("gmail", connect)

    @Slot(bool)
    def chooseGmailClient(self, persist):
        if self._busy:
            return
        path, _ = QFileDialog.getOpenFileName(
            None, "Google Desktop OAuth client", "", "JSON (*.json)"
        )
        if path:

            def configure():
                config = google_desktop_client(json.loads(Path(path).read_text(encoding="utf-8")))
                self.vault.save("google-oauth-client", json.dumps(config), persist)
                self.feedback("Google OAuth client configured. Click Connect Gmail to sign in.")

            self.local(configure)

    @Slot(str, bool)
    def connectOutlook(self, client_id, persist):
        self.connectMailbox(
            "outlook",
            lambda: connect_outlook(self.tracker, self.vault, client_id.strip(), persist),
        )

    @Slot(str)
    def saveMicrosoftClient(self, client_id):
        def configure():
            from uuid import UUID

            value = str(UUID(client_id.strip()))
            self.tracker.set_setting("microsoft_client_id", value)
            self.feedback("Microsoft OAuth client configured. Click Connect Outlook to sign in.")

        self.local(configure)

    def connectMailbox(self, provider, action):
        name = "Gmail" if provider == "gmail" else "Outlook"
        if self._busy:
            self._mailbox_messages[provider] = f"{name}: pause the scan or wait before connecting."
            self.feedback(self._mailbox_messages[provider])
            return
        self._mailbox_messages[provider] = (
            f"{name}: signing in. Finish in your browser, then return here."
        )
        self.feedback(self._mailbox_messages[provider])

        def complete(address):
            self._mailbox_messages[provider] = f"{name}: connected read-only."
            self.feedback(f"Connected {address} read-only.")

        def failed(text):
            self._mailbox_messages[provider] = f"{name}: connection was not saved. {text}"

        self.background(action, complete, operation=f"oauth:{provider}", on_failure=failed)

    @Slot(int)
    def disconnectAccount(self, account_id):
        def action():
            with self.tracker.db.sessions.begin() as session:
                account = session.get(Account, account_id)
                if account and account.credential_ref:
                    self.vault.remove(account.credential_ref)
                    account.credential_ref = ""
                    self._mailbox_messages.pop(account.provider, None)

        self.local(action)

    @Slot(int, result=str)
    def historyStart(self, months):
        today = datetime.now(UTC).date()
        index = today.year * 12 + today.month - 1 - months
        year, month = divmod(index, 12)
        month += 1
        return date(year, month, min(today.day, calendar.monthrange(year, month)[1])).isoformat()

    @Slot(str, str)
    def previewHistory(self, start, end):
        provider = self._provider

        def preview():
            since = date.fromisoformat(start).isoformat() + "T00:00:00+00:00"
            until = (date.fromisoformat(end) + timedelta(days=1)).isoformat() + "T00:00:00+00:00"
            return self.importer.preview(since, until, provider)

        def complete(plan):
            self._scan_plan = plan | {"search_id": self._search_id}
            self._estimate = plan["estimate"] | {"total": plan["total"]}
            self.scanReady.emit()

        self.background(preview, complete, operation="scan")

    @Slot(float)
    def startHistory(self, budget):
        if not self._scan_plan or self._scan_plan["search_id"] != self._search_id:
            self.feedback("Preview the email range for this search first.")
            return
        if not self.apiReady:
            self.feedback("Add your API key in Settings first.")
            return
        plan, search_id = self._scan_plan, self._search_id

        def run():
            scan_id = self.importer.create_scan(search_id, plan, budget)
            return self.importer.run(scan_id, plan, self._work.report_progress)

        self.background(run, self.scanFinished, operation="scan")

    def scanFinished(self, scan):
        self.feedback(
            f"Scan {scan['state']}. Recorded usage/reservations: ${scan['spent']:.4f} USD. "
            + scan.get("error", "")
        )

    @Slot()
    def pauseScan(self):
        self.importer.cancelled.set()
        self.feedback("Pausing after the current request. Completed work will be kept.")

    @Slot(int, float)
    def resumeScan(self, scan_id, budget):
        self.background(
            lambda: self.importer.resume(scan_id, budget, self._work.report_progress),
            self.scanFinished,
            operation="scan",
        )

    @Slot(int)
    def removeImport(self, scan_id):
        def hide():
            self.importer.hide_scan(scan_id, self._search_id)
            self.feedback("Import removed from history. Job records and saved emails were kept.")

        self.local(hide)

    @Slot()
    def poll(self):
        if self._busy or not self.aiEnabled or not self.apiReady:
            return
        if any(item["state"] != "completed" for item in self._scans):
            return
        selected = next(item for item in self._searches if item["id"] == self._search_id)
        if selected["archived"]:
            return
        provider = self._provider
        accounts = [
            item
            for item in self._accounts
            if item["connected"] and (provider == "all" or item["provider"] == provider)
        ]
        if not accounts:
            return
        with self.tracker.db.sessions() as session:
            spent = sum(
                session.scalars(
                    select(Usage.cost).where(
                        Usage.created_at >= datetime.now(UTC).date().isoformat()
                    )
                )
            )
        budget = min(float(self.syncBudget), float(self.dailyBudget) - spent)
        if budget <= 0:
            self.feedback("Daily AI spending limit reached. Automatic sync is paused.")
            return
        end = datetime.now(UTC).isoformat(timespec="seconds")
        start = min(item["last_sync"] or end for item in accounts)
        start = (datetime.fromisoformat(start) - timedelta(minutes=5)).isoformat(timespec="seconds")
        search_id = self._search_id

        def run():
            plan = self.importer.preview(start, end, provider)
            scan_id = self.importer.create_scan(search_id, plan, budget)
            result = self.importer.run(scan_id, plan, self._work.report_progress)
            if result["state"] == "completed":
                with self.tracker.db.sessions.begin() as session:
                    for item in accounts:
                        session.get(Account, item["id"]).last_sync = end
            return result

        self.background(run, self.scanFinished, operation="scan")

    def stop(self):
        self._closing = True
        self.timer.stop()
        self.refresh_timer.stop()
        self.importer.cancelled.set()
        self.pool.waitForDone()
        self.read_pool.waitForDone()
