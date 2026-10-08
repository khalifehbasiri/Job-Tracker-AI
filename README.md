# Job Tracker AI

[![Checks](https://github.com/khalifehbasiri/Job-Tracker-AI/actions/workflows/checks.yml/badge.svg)](https://github.com/khalifehbasiri/Job-Tracker-AI/actions/workflows/checks.yml)

A Windows-first, open-source desktop app that tracks job applications from your email. Your records live in a local SQLite database. Optional AI processing uses **your own OpenAI API key**.

![Desktop dashboard with fictional records](docs/images/dashboard.png)

## What works in this developer release

- Separate named job searches, with optional dates, archiving, and application moves between searches.
- Dashboard, company/role search, stage filtering, editable applications, notes, event timelines, and upcoming tasks.
- Excel column-mapping preview and duplicate detection. Export each search to a workbook with Applications, Events, Tasks, and Search sheets. Import/export costs no API credits.
- First-run setup wizard, offline step-by-step guide, and read-only Gmail/Outlook browser sign-in using your own OAuth registration. Select Gmail, Outlook, or all mailboxes for new scans and automatic processing.
- GPT-6 Luna Decisions classifies application confirmations, rejections, assessments, interviews, offers, and other updates; GPT-5.4 mini extracts facts and dates. Uncertain matches go to a review inbox.
- Historical email scans for 1, 3, 6, or 12 months, plus custom dates. Process oldest first across connected mailboxes. Preview volume and illustrative API costs, set a USD spending limit, then start. Pause and resume without repeating completed AI work. Invalid AI extractions go to review without automatic paid retries.
- Masked API-key settings, secure OS credential storage, and session-only credentials. No shared developer key.
- Opt-in polling every five minutes with per-sync and daily AI spending limits. Closing to the tray keeps the worker running while your computer is awake.
- Database backups and automatic schema migrations. Manual status corrections are protected from automatic updates.

**Development preview: email onboarding is still in development.** Users must create their own Google Desktop OAuth registration or Microsoft application client ID, and supply their own OpenAI API key. No project-owned OAuth configuration or user credentials are bundled. Follow the detailed [setup guide](docs/mailbox-setup.md), also available offline inside the app. Automated tests use fake mailboxes and API responses; broad real-account validation remains pending. Project-owned public sign-in is a future milestone; see [public OAuth preparation](docs/public-oauth.md).

## Run on Windows

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git, then open PowerShell:

```powershell
git clone https://github.com/khalifehbasiri/Job-Tracker-AI.git
cd Job-Tracker-AI
uv sync --locked
uv run job-tracker
```

uv installs the required Python 3.13 runtime. If you installed uv through pip and it is not on PATH, use `python -m uv` in place of `uv`.

Preview the dashboard with fictional records in a separate database:

```powershell
uv run job-tracker --demo
```

For your own records, create a search and add applications or import your existing `.xlsx` workbook from Applications. Manual tracking works without an API key or email connection.

To enable email processing, follow the welcome wizard or configure your own OAuth registration in Settings, connect a mailbox, save your OpenAI key, and preview a scan in Email history. Automatic processing is disabled until you explicitly enable it. The first mailbox connection starts from the present; use a historical scan to reconstruct older applications.

## Costs and privacy

API usage is billed to your OpenAI account; a ChatGPT subscription does not include API credits. Cost depends on message length and how many messages need extraction. A year of email is not automatically expensive: the app shows volume and illustrative estimates before you start. Long messages and retries can exceed those illustrations. Reservations stop a scan before dispatching a request that would exceed its app budget, using the configured price constants; the OpenAI billing dashboard remains the source of truth.

Credentials are stored through the OS keyring, or in memory for session-only use. The default database stays in your local application-data directory, outside this repository and OneDrive. Its path is shown in Settings. **The database is not encrypted by the app and includes normalized email text.** Keep backups private.

Email is treated as untrusted data. Models cannot send emails, follow links, or run tools. Attachments are not downloaded. Selected message text goes directly to OpenAI when you start an AI scan or enable automatic processing. There is no developer backend or telemetry. Read the [privacy details](PRIVACY.md).

## Development

```powershell
uv run ruff check .
uv run ruff format --check .
$env:QT_QPA_PLATFORM = "offscreen"
$env:QT_QUICK_BACKEND = "software"
uv run pytest -q
uv build
```

See [architecture](docs/architecture.md), [contributing](CONTRIBUTING.md), and [next milestones](docs/roadmap.md). Windows and Linux CI check formatting, behavior, QML rendering, and distributable Python packages. Windows is the primary desktop target; other platforms need a supported OS keyring or session-only credentials.

## License

Application code is [MIT licensed](LICENSE). Dependencies retain their own licenses. PySide6/Qt distributions have LGPL/GPL or commercial terms; binary releases must preserve applicable dependency notices and comply with those terms.
