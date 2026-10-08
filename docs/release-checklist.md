# Preview release checklist

## Implemented

- First-run wizard: named search, provider setup, OpenAI key, opt-in polling/budgets.
- Gmail/Outlook/all-mailboxes selection for new scans and automatic processing.
- User-owned OAuth configuration; no maintained registration bundled or used by CI.
- Masked keys, OS credential persistence, session-only mode, reconnect/disconnect.
- Safe errors for provider authorization/storage failures and OpenAI status codes.
- Key check uses model metadata; no mailbox content and no inference request.
- Offline and repository setup guides with complete registration steps.
- Oldest-first imports, review recovery, resumable scans, Excel snapshots.
- PyInstaller folder bundle, Inno Setup per-user installer, dependency notices.
- Frozen demo smoke test: QML rendering, SQLite migrations/integrity, no accounts.
- ZIP, installer, SHA-256 checksums, and tag-triggered draft release automation.

## Validate before publishing a preview download

- [ ] Confirm Windows release workflow builds on GitHub's clean runner.
- [ ] Install, upgrade, and uninstall using an isolated Windows account/VM; confirm shortcuts and records are preserved.
- [ ] Confirm email credentials survive restart, reconnect, and disconnect with a consenting Gmail account and a personal Outlook mailbox.
- [ ] Confirm both real AI endpoints work for a newly created OpenAI project, using consenting data and an explicit spending limit.
- [ ] Review notices and corresponding-source distribution requirements for every bundled Qt module; source pointers alone are not a completed licensing audit.
- [ ] Check installer version matches the tag; review generated assets and release notes, then publish the draft.

## Remaining for an ordinary-user production launch

- Project-owned Google public OAuth verification and applicable security assessment.
- Microsoft publisher verification for broader work/school adoption; tenant consent policies still apply.
- A domain-verifiable homepage/privacy site for project-owned Google onboarding.
- In-app account-history erasure and retention settings.
- A disclosed paid fictional-data AI test that verifies Decisions and extraction.
- Configurable supported models/pricing, classifier/matching calibration, and timezone improvements.
- Windows code signing certificate and signing workflow. Preview binaries are unsigned.

The source repository can be public while these items remain. A preview release
must disclose its limits; it is not a claim of provider approval or production readiness.
