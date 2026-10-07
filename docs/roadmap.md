# Release milestones

## Available now: developer source release

Desktop dashboard, search-scoped SQLite records, manual editing, Excel import/export, OAuth adapters, constrained AI extraction, review inbox, resumable history scanning, credentials, budgets, and tray polling. Automated validation uses fictional email fixtures and rendered QML pages.

## Before a wider end-user release

- Validate Gmail, Outlook, Decisions, and extraction end to end with consenting test accounts.
- Calibrate classification thresholds and identity matching with redacted, labelled examples; measure missed job emails and incorrect matches.
- Complete Google restricted-scope verification and security assessment, plus Microsoft publisher verification. Maintained desktop clients, build-secret configuration, normal sign-in buttons, and provider diagnostics are implemented; approval and a domain ownership-verifiable privacy site remain pending. See [public OAuth preparation](public-oauth.md).
- Build and sign a Windows installer, include dependency licenses, and verify upgrades and uninstall behavior on a clean machine.
- Add an explicit data retention/erase flow, connection diagnostics with safe error messages, and configurable model/pricing updates.
- Improve editable task scheduling, assessment completion tracking, timezone display, and review corrections before acceptance.

## Later possibilities

Opt-in launch at login, desktop reminders, additional AI providers/local models, richer Excel column transformations, and macOS/Linux packaging. These are not included in the current release.
