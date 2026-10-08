# Job Tracker AI v0.2.0 — self-configured edition

An open-source Windows desktop app that uses OpenAI Decisions with GPT-6 Luna
for email classification and GPT-5.4 mini with structured extraction to build
application records, event history, and a searchable review inbox.

Windows x64 downloads need no Python installation:

- **Job-Tracker-AI-Setup.exe**: per-user installer with shortcuts and uninstall support.
- **Job-Tracker-AI-Windows-x64.zip**: unzip the whole folder, then run Job-Tracker-AI.exe.
- **Job-Tracker-AI-Setup-Guide.html**: standalone instructions you can open in a browser, also included in the app.
- **Job-Tracker-AI-Dependency-Sources.zip**: matching Qt/PySide/certifi sources, provenance, hashes, and library replacement instructions.
- **SHA256SUMS.txt**: checksums for all downloadable assets.

## User-owned credentials

This release intentionally requires your own **OpenAI API key** and **Google
Desktop OAuth registration or Microsoft Application client ID**. No shared
project-owned sign-in configuration or user credentials are bundled. The welcome
wizard and complete offline guide explain each registration step. Open **Help &
setup guide** from the sidebar or press **F1**. The installer also creates a guide
Start menu shortcut. Shared one-click onboarding is outside this release's scope.

Choose Gmail, Outlook, or all mailboxes for new history scans and automatic
processing. Existing job records remain visible. Automatic processing is off by
default; connecting email does not start AI processing.

## Included behavior

- Separate named searches, application editing, event timelines, tasks, and per-search Excel export with dropdowns.
- Oldest-first historical imports, spending limits, durable queues, cached AI results, pause/resume, and restart recovery.
- Collapsed/searchable review cards, clear unmatched update records, and confirmation-only applied dates.
- Search metadata editing, removable import history preserving records/usage, light/dark mode, and contextual setup help.
- Read-only connectors, OS-backed credential storage, and optional session-only credentials.

Historical imports now keep navigation, local search, review expansion, and Pause
responsive. Database refreshes and timelines run in a separate background worker;
progress no longer rebuilds the entire interface. Interrupted imports offer
Resume after restarting, preserving completed records and recorded usage.

## Validation and disclosed limits

Automated tests use fictional mail and fake model responses. Windows/Linux checks,
frozen launch/rendering/integrity tests, and isolated cross-version installer tests
cover integration behavior and record preservation. They do not establish measured
classifier accuracy or compatibility with every real provider account.

Decisions is currently an OpenAI public-beta API; your project must have access.
The build is unsigned. Google/Microsoft account consent policies still apply.

AI sends selected email text to OpenAI and uses your API credits. Manual tracking
and Excel import/export have no API costs. Records stay in local, unencrypted
SQLite. Uninstalling preserves the database and OS credentials.

Quit completely from the tray before upgrading. See README, the setup guide, PRIVACY.md, and
docs/release-checklist.md for limitations and validation status.
