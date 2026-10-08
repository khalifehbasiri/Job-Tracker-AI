# Release milestones

## Implemented for the development preview

Desktop dashboard, named searches, SQLite migrations, manual editing, Excel import/export, constrained AI extraction, review inbox, resumable oldest-first history scans, budgets, and tray polling.

Editable search metadata; confident unmatched job-update records; confirmation-only applied dates and local repair; searchable/collapsed reviews; import-history hiding without deleting records; Excel dropdowns; saved light/dark themes; contextual help; generated app/installer logo; fictional demo screenshots and engineering portfolio documentation.

The welcome wizard and offline guide cover user-owned Google/Microsoft OAuth registrations, OpenAI keys, search creation, and opt-in processing. Gmail/Outlook/all-mailboxes selection controls new scans and polling. Safe connection diagnostics, reconnect/disconnect, masked inputs, OS credential storage, and session-only mode are implemented.

Windows packaging uses a PyInstaller folder bundle and Inno Setup per-user installer. Builds produce a portable ZIP, installer, checksums, dependency notices, and a frozen-app demo smoke test. GitHub Actions uploads build artifacts and creates draft prereleases for version tags. No project-owned OAuth credentials are bundled.

## Before publishing preview downloads

Follow [the release checklist](release-checklist.md): complete clean-runner packaging, isolated install/upgrade/uninstall validation, corresponding-source/licensing review, and consenting real-account tests. The source repository can remain public while these checks are pending.

## Before ordinary-user production onboarding

- Validate Gmail, Outlook, Decisions, and extraction with newly configured accounts and bounded paid usage.
- Finish in-app account-history erasure and retention controls.
- Add the disclosed paid fictional-email AI test; Check key currently verifies extraction-model metadata only.
- Calibrate classification thresholds and identity matching using redacted labelled examples.
- Prepare project-owned public OAuth, including Google restricted-scope review/security assessment and a domain-verifiable homepage/privacy site. Microsoft publisher verification helps organizational adoption but is not a universal requirement for personal Outlook access. See [public OAuth preparation](public-oauth.md).
- Configure supported model/pricing updates and improve scheduling, timezone display, and review corrections.
- Obtain a code-signing certificate and sign Windows releases. Preview binaries are unsigned.

## Later possibilities

Opt-in launch at login, desktop reminders, additional AI providers/local models, richer Excel transformations, and macOS/Linux packaging.
