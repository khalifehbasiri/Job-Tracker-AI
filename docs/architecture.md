# Architecture and product scope

## Desktop runtime

Python 3.13, PySide6 with Qt Quick/QML, SQLite through SQLAlchemy, Alembic migrations, Pydantic validation, openpyxl import/export, and OS-backed keyring credentials. The GUI runs on the main thread; serialized background jobs run outside it. Network calls never hold database transactions open.

Data is stored in the platform's local application-data directory, outside the checkout and cloud-sync folders. SQLite enables foreign keys, WAL, and a busy timeout. The desktop holds an OS file lock for its database so a second desktop cannot make competing AI requests. The live database is not synchronized through OneDrive; SQLite backup snapshots and Excel exports may be.

## Job searches

Each application belongs to one named search. Searches have optional dates and an archive state. Views, reviews, history imports, and exports are scoped to the selected search. Late emails match existing application identities before assigning new applications to a search. Ambiguous assignments require review.

## Email and AI

Gmail and Outlook use read-only OAuth. Development users configure their own installed-app OAuth clients. A maintained, verified OAuth registration is a release prerequisite for turnkey public mailbox onboarding.

Inbound emails are untrusted data, never instructions. The classifier has no tools or mail mutation privileges. Decisions classifies relevance and event type; a mini model extracts typed fields and evidence. Python validates results, matches application identity, and updates an append-only event history. Manual corrections are preserved. Silence is not rejection; an invitation is not completion.

## Historical import and spending

Import from email history supports 1, 3, 6, and 12 months plus custom dates. Count unprocessed messages, show a conservative token-based cost estimate, then request a user-selected budget and explicit start. Persist scan state and usage; allow cancellation and resuming. Deduplicate message IDs within each account and reuse results across overlapping imports. Reserve worst-case per-request costs before sending requests and stop before the budget is exhausted. Estimates are not provider billing statements.

## Credentials and offline operation

Settings offers masked OpenAI key entry, save/test/remove, and optional session-only storage. Never write secrets to SQLite, logs, exports, or Git. No secure credential backend means session-only operation. Manual records, dashboards, and Excel import/export require no API key. Email and AI require network connectivity.

## Reliability and release scope

Incremental Git commits group coherent changes. Tests cover search isolation, matching, duplicate and delayed events, retries, budget enforcement, credential handling, and exports. API tests use fixtures and fakes: development does not spend a user's credits or read their inbox. Start with preview/review for uncertain changes and calibrate thresholds against labelled email samples.

Window close minimizes to tray when available. Explicit quit stops the worker. Sync catches up after startup/sleep; the app cannot process email while the computer is off. Optional login startup and signed installers are later release work.
