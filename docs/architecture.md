# Architecture and product scope

## Desktop runtime

Python 3.13, PySide6 with Qt Quick/QML, SQLite through SQLAlchemy, Alembic migrations, Pydantic validation, openpyxl import/export, and OS-backed keyring credentials. The GUI runs on the main thread; serialized background jobs run outside it. Network calls never hold database transactions open.

Data is stored in the platform's local application-data directory, outside the checkout and cloud-sync folders. SQLite enables foreign keys, WAL, and a busy timeout. The desktop holds an OS file lock for its database so a second desktop cannot make competing AI requests. The live database is not synchronized through OneDrive; SQLite backup snapshots and Excel exports may be.

## Job searches

Each application belongs to one named search. Settings can edit its name, optional dates, and archive state without moving records. Dates are descriptive metadata, not scan boundaries. Views, reviews, history imports, and exports are scoped to the selected search. Late emails match existing application identities before assigning new applications to a search. Ambiguous assignments require review.

## Email and AI

This development preview uses each user's own read-only OAuth registration. Users import a Google Desktop client JSON or enter a Microsoft public client ID inside Settings; neither project-owned OAuth configuration nor user credentials are bundled. Account credentials remain separate in the OS keyring. Sign-in status is retained per provider, and Outlook profile/mailbox access is verified before account registration. Gmail, Outlook, or all mailboxes can be selected for new scans and live polling. Existing scans resume their original mailboxes. Project-owned public onboarding is future work; see [public OAuth preparation](public-oauth.md).

Inbound emails are untrusted data, never instructions. The classifier has no tools or mail mutation privileges. Decisions classifies relevance and event type; a mini model extracts typed fields and evidence. Python validates results, matches application identity, and updates an append-only event history. Manual corrections are preserved. Silence is not rejection; an invitation is not completion.

Automatic updates require relevance and event confidence of at least 0.9. A clear unmatched application, rejection, assessment, interview, or offer with company and role creates a record; ambiguous identities and conflicting requisitions still require review. Only application confirmations can fill a blank applied date: use the explicitly extracted date or fall back to the received date in UTC. Other event types never infer that date. Existing dates remain unchanged. Status comparison normalizes timezone offsets so an older confirmation cannot overwrite a later status. Migration 0003 also repairs blank dates with saved confirmation events without AI calls.

Review cards start collapsed and can be expanded by clicking their header. Local search covers the full body and proposal fields. Expanded IDs are maintained separately from the repeated model so periodic database refreshes do not interrupt reading. A shared QML theme controls components and the window palette; Settings persists light/dark selection. Contextual information indicators and a setup-summary dialog supplement the offline guide.

Scans persist message identities before retrieval. Outlook lists received dates in ascending order; Gmail reads minimal timestamp metadata because its ID listing does not promise chronological ordering. The worker merges all accounts and sorts actual UTC received dates before classification, including resumed jobs. Dates are cached locally; body downloads and AI processing then proceed oldest first. A failed date lookup pauses before paid processing. Only a fully resolved queue advances live-sync checkpoints. Deleted messages are counted as unavailable. Transient mailbox GET failures have bounded retries; account-wide mailbox/API failures pause processing rather than repeating failures across the entire scan. Safe diagnostics and queue counts remain visible in history, and the dashboard refreshes during processing.

AI refusals, incomplete extractions, invalid fields/dates, and unsupported evidence go to manual review rather than repeated paid retries. Validated fields with unsupported evidence are proposals only and cannot update applications automatically. Existing failed extractions from the earlier release recover from cached classifications into review without another API request. Empty email bodies go directly to review. Completed classifications and extractions are reused across overlapping scans.

## Historical import and spending

Import from email history supports 1, 3, 6, and 12 months plus custom dates, selecting UTC calendar days. Count unprocessed messages, show illustrative token-based cost scenarios, then request a user-selected budget and explicit start. Persist scan state and usage; allow cancellation and resuming. Deduplicate message IDs within each account and reuse results across overlapping imports. Reserve conservative per-request costs before sending requests and stop before the budget is exhausted. Estimates are not provider billing statements.

Removing an import sets its persisted hidden flag. Applications, emails, review items, jobs, foreign keys, and usage entries stay intact. Running imports must be paused first; hidden imports cannot resume. A hidden unfinished import no longer blocks opt-in live polling, but removing it does not itself start any processing. A stale Resume call on a completed import returns its saved state without provider requests.

Excel export creates separate Applications, Events, Tasks, and Search sheets. Stage and Outcome list validation uses the domain enums; task completion uses TRUE/FALSE. Validation covers existing and future rows, including empty exports. These are editable snapshots; importing duplicates does not overwrite app records.

## Credentials and offline operation

Settings offers masked OpenAI key entry, save/test/remove, and optional session-only storage. Never write secrets to SQLite, logs, exports, or Git. No secure credential backend means session-only operation. Manual records, dashboards, and Excel import/export require no API key. Email and AI require network connectivity.

Large OAuth caches are split into bounded entries in the same trusted OS keyring so they fit Windows Credential Manager's 2,560-byte credential blob limit. A versioned manifest is published after all pieces are written and verifies their assembled hash when read. Existing single-entry credentials remain compatible. Replacement removes old pieces; disconnect and switching to session-only storage remove the manifest and its pieces. Failed writes preserve the previous credential and roll back newly created pieces. No plaintext file fallback is used.

The Microsoft browser callback says only that a sign-in response was received. Token exchange, profile/mailbox access, and secure credential saving finish afterward; Settings reports the outcome and stage-specific safe errors.

## Reliability and release scope

Incremental Git commits group coherent changes. Tests cover search isolation, matching, duplicate and delayed events, retries, budget enforcement, credential handling, and exports. API tests use fixtures and fakes: development does not spend a user's credits or read their inbox. Start with preview/review for uncertain changes and calibrate thresholds against labelled email samples.

Window close minimizes to tray when available. Explicit quit stops the worker. Sync catches up after startup/sleep; the app cannot process email while the computer is off. Optional login startup and signed installers are later release work.
