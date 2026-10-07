# Architecture and product scope

## Desktop runtime

Python 3.13, PySide6 with Qt Quick/QML, SQLite through SQLAlchemy, Alembic migrations, Pydantic validation, openpyxl import/export, and OS-backed keyring credentials. The GUI runs on the main thread; serialized background jobs run outside it. Network calls never hold database transactions open.

Data is stored in the platform's local application-data directory, outside the checkout and cloud-sync folders. SQLite enables foreign keys, WAL, and a busy timeout. The desktop holds an OS file lock for its database so a second desktop cannot make competing AI requests. The live database is not synchronized through OneDrive; SQLite backup snapshots and Excel exports may be.

## Job searches

Each application belongs to one named search. Searches have optional dates and an archive state. Views, reviews, history imports, and exports are scoped to the selected search. Late emails match existing application identities before assigning new applications to a search. Ambiguous assignments require review.

## Email and AI

Gmail and Outlook use read-only OAuth through maintained public desktop registrations. Google build metadata is generated from an ignored local file or an encrypted GitHub Actions secret. Forks can override registrations in Advanced OAuth setup. Account credentials remain separate in the OS keyring. Sign-in status is retained per provider, and Outlook profile/mailbox access is verified before account registration. Maintained clients are wired in, but provider approval remains a release prerequisite for general public onboarding; see [public OAuth preparation](public-oauth.md).

Inbound emails are untrusted data, never instructions. The classifier has no tools or mail mutation privileges. Decisions classifies relevance and event type; a mini model extracts typed fields and evidence. Python validates results, matches application identity, and updates an append-only event history. Manual corrections are preserved. Silence is not rejection; an invitation is not completion.

Scans persist message identities before retrieval. Outlook lists received dates in ascending order; Gmail reads minimal timestamp metadata because its ID listing does not promise chronological ordering. The worker merges all accounts and sorts actual UTC received dates before classification, including resumed jobs. Dates are cached locally; body downloads and AI processing then proceed oldest first. A failed date lookup pauses before paid processing. Only a fully resolved queue advances live-sync checkpoints. Deleted messages are counted as unavailable. Transient mailbox GET failures have bounded retries; account-wide mailbox/API failures pause processing rather than repeating failures across the entire scan. Safe diagnostics and queue counts remain visible in history, and the dashboard refreshes during processing.

AI refusals, incomplete extractions, invalid fields/dates, and unsupported evidence go to manual review rather than repeated paid retries. Validated fields with unsupported evidence are proposals only and cannot update applications automatically. Existing failed extractions from the earlier release recover from cached classifications into review without another API request. Empty email bodies go directly to review. Completed classifications and extractions are reused across overlapping scans.

## Historical import and spending

Import from email history supports 1, 3, 6, and 12 months plus custom dates, selecting UTC calendar days. Count unprocessed messages, show illustrative token-based cost scenarios, then request a user-selected budget and explicit start. Persist scan state and usage; allow cancellation and resuming. Deduplicate message IDs within each account and reuse results across overlapping imports. Reserve conservative per-request costs before sending requests and stop before the budget is exhausted. Estimates are not provider billing statements.

## Credentials and offline operation

Settings offers masked OpenAI key entry, save/test/remove, and optional session-only storage. Never write secrets to SQLite, logs, exports, or Git. No secure credential backend means session-only operation. Manual records, dashboards, and Excel import/export require no API key. Email and AI require network connectivity.

## Reliability and release scope

Incremental Git commits group coherent changes. Tests cover search isolation, matching, duplicate and delayed events, retries, budget enforcement, credential handling, and exports. API tests use fixtures and fakes: development does not spend a user's credits or read their inbox. Start with preview/review for uncertain changes and calibrate thresholds against labelled email samples.

Window close minimizes to tray when available. Explicit quit stops the worker. Sync catches up after startup/sleep; the app cannot process email while the computer is off. Optional login startup and signed installers are later release work.
