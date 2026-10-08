<img src="docs/images/logo.png" width="88" alt="Job Tracker AI logo">

# Job Tracker AI

[![Checks](https://github.com/khalifehbasiri/Job-Tracker-AI/actions/workflows/checks.yml/badge.svg)](https://github.com/khalifehbasiri/Job-Tracker-AI/actions/workflows/checks.yml)
[![Windows release build](https://github.com/khalifehbasiri/Job-Tracker-AI/actions/workflows/windows-release.yml/badge.svg)](https://github.com/khalifehbasiri/Job-Tracker-AI/actions/workflows/windows-release.yml)

A Windows-first, open-source **AI application** that turns job-search emails into structured application records. It combines the **OpenAI Decisions API with GPT-6 Luna**, **GPT-5.4 mini through the Responses API**, deliberately constrained prompts, and deterministic Python workflows to classify messages, extract evidence, and update a local SQLite database.

Built to demonstrate applied AI engineering: integrating model APIs into a usable desktop product, handling uncertain outputs, controlling inference costs, protecting credentials, and recovering from failures. Users provide their own OpenAI API key and Google/Microsoft OAuth registration. Manual tracking and Excel workflows also work offline.

[AI engineering walkthrough](docs/ai-engineering.md) · [Engineering portfolio](#engineering-portfolio-for-recruiters-and-teams) · [Credential setup](docs/mailbox-setup.md) · [Architecture](docs/architecture.md) · [Release checklist](docs/release-checklist.md)

![Desktop dashboard with fictional records](docs/images/dashboard.png)

## AI engineering at a glance

| Responsibility | Implementation | Why it matters |
| --- | --- | --- |
| Decide which messages matter | One Decisions request asks a named `predicate` for job relevance and a named `choice` for application event type. | Separates a bounded classification decision from generating application details. |
| Extract facts | A second request uses GPT-5.4 mini, Responses, and a strict JSON schema generated from Pydantic. Unrelated messages skip extraction. | Spend on extraction only when needed; keep the response compatible with the app's data model. |
| Design prompts | Explicit event definitions, quoted-history rules, missing-value handling, date/timezone requirements, and exact evidence excerpts. | Make task boundaries and abstention behavior part of the interface contract. |
| Validate before acting | Python checks fields, evidence against the source body, confidence, application identity, event chronology, and manual overrides. | Schema-valid output still needs factual and business-rule checks. |
| Route uncertainty | Low confidence, conflicting identities, unsupported evidence, and incomplete responses enter a searchable review inbox. | A human can resolve uncertainty without repeated automatic inference. |
| Operate the workflow | Durable jobs, persisted results, spending reservations, reported-token settlement, safe diagnostics, and separate import/read workers. | Model integration includes recovery, cost management, and a responsive user experience. |

```mermaid
flowchart TD
    Mail[Read-only email connectors] --> Queue[Durable worker queue: oldest first]
    Queue --> Decide[Decisions API · GPT-6 Luna<br/>Relevance predicate + event choice]
    Decide -->|Relevance below 0.1| Skip[Save result; skip extraction]
    Decide -->|Potential application email| Extract[Responses API · GPT-5.4 mini<br/>Strict JSON schema + evidence]
    Extract --> Checks[Python validation<br/>Evidence, identity, confidence, chronology]
    Checks -->|Clear, supported result| Records[(SQLite records + event history)]
    Checks -->|Uncertain or invalid| Review[Human review inbox]
    Review --> Records
    Records --> Dashboard[Desktop dashboard / Excel export]
```

The design uses the APIs for their respective tasks: [Decisions returns typed classification answers](https://developers.openai.com/api/docs/guides/decisions); [Structured Outputs constrains extraction to a schema](https://developers.openai.com/api/docs/guides/structured-outputs). Decisions is currently a provider public-beta API. The app does not claim measured classifier accuracy or treat model confidence as a calibrated guarantee.

## Prompt engineering in the implementation

The prompts are reviewable code in [`ai.py`](src/job_tracker/ai.py): `QUESTIONS` defines relevance and event classification, `INSTRUCTIONS` defines extraction, and `payload()` separates sender, subject, received date, and body into JSON fields. The model has no tools or mailbox write permissions.

| Prompt rule | Failure it addresses | Enforcement outside the prompt |
| --- | --- | --- |
| Classify the latest message; ignore quoted earlier events. | A rejection email includes an older application confirmation. | Event chronology prevents an older confirmation from overwriting a newer status. |
| Return null for absent facts. | Invented company, role, requisition, or date. | Pydantic validates types/dates; missing identity fields cannot trigger automatic creation. |
| The received timestamp is not an explicitly stated application date. | A rejection or interview date becomes Date applied. | Only confirmation events may fill a blank applied date, with a documented UTC fallback. |
| Deadline/interview timestamps require an explicit date, time, and timezone. | An ambiguous time becomes a misleading calendar commitment. | Invalid or unsupported values go to review. |
| Evidence must be a short exact excerpt from the supplied body. | An otherwise valid JSON object contains invented supporting text. | Python checks the excerpt against the email before automatic updates. This is a grounding check, not proof every field is correct. |
| Email content is untrusted data, never instructions. | Email text attempts to change the extraction task or execute actions. | No tools, link-following, sending, deleting, or marking messages read. Prompt instructions alone are not a complete injection defense. |

Prompts and schemas are committed alongside tests. Classification results retain the model and prompt version in the local cache. Changing a prompt does not silently reclassify old mail or charge for a new pass. See the [walkthrough](docs/ai-engineering.md) for request contracts, decision thresholds, failure handling, and the evaluation work still needed before claiming accuracy.

## Product features

- Separate named job searches, with editable names/dates, archiving, and application moves between searches. Every search has its own Excel export.
- Dashboard, company/role search, stage filtering, editable applications, notes, event timelines, and upcoming tasks.
- Excel column-mapping preview and duplicate detection. Export Applications, Events, Tasks, and Search sheets with dropdowns for Stage, Outcome, and task Completed fields. Import/export costs no API credits.
- First-run setup wizard, offline step-by-step guide, and read-only Gmail/Outlook browser sign-in using your own OAuth registration. Select Gmail, Outlook, or all mailboxes for new scans and automatic processing.
- GPT-6 Luna Decisions classifies application confirmations, rejections, assessments, interviews, offers, and other updates; GPT-5.4 mini extracts structured facts and dates with evidence. Clear unmatched updates can create records automatically. Uncertain matches go to a collapsed, expandable review inbox with full-text search.
- Historical email scans for 1, 3, 6, or 12 months, plus custom dates. Process oldest first across connected mailboxes. Preview volume and illustrative API costs, set a USD spending limit, then start. Pause and resume without repeating completed AI work. Invalid AI extractions go to review without automatic paid retries.
- Masked API-key settings, secure OS credential storage, and session-only credentials. No shared developer key.
- Opt-in polling every five minutes with per-sync and daily AI spending limits. Minimize the window to keep the worker running while your computer is awake; closing the window quits the app.
- Database backups and automatic schema migrations. Manual status corrections are protected from automatic updates.
- Saved light/dark mode, contextual hover indicators, and an in-app credential setup summary with links to the complete offline and online guides.
- Remove import-history entries without deleting applications, saved emails, reviews, or usage records. Completed imports have no Resume button.

**This release uses user-owned credentials.** Create your own Google Desktop OAuth registration or Microsoft application client ID and supply your OpenAI API key. No project-owned OAuth configuration or user credentials are bundled. Shared one-click onboarding is outside this release's scope. Follow the detailed [setup guide](docs/mailbox-setup.md): open **Help & setup guide** in the sidebar or press **F1** to read its bundled HTML version offline. Automated tests use fake mailboxes and API responses; their results do not establish broad real-account compatibility. Project-owned public sign-in is a future milestone; see [public OAuth preparation](docs/public-oauth.md).

## More demo screens

All screenshots use fictional applications and email text, with no real mailbox credentials or paid API calls.

<details>
<summary>Dark dashboard, applications, review inbox, imports, and settings</summary>

**Dark dashboard**

![Dark dashboard](docs/images/dashboard-dark.png)

**Applications**

![Searchable applications with stage and outcome](docs/images/applications.png)

**Collapsed review inbox**

![Collapsed, searchable review inbox](docs/images/review-inbox.png)

**Import history**

![Completed import with Remove and no Resume](docs/images/email-history.png)

**Dark settings**

![Appearance, search editing, and credential settings](docs/images/settings-dark.png)

</details>

## Engineering portfolio for recruiters and teams

I built the integration between probabilistic model outputs and a stateful desktop application. The main engineering challenge was turning emails into useful records while managing ambiguity, identity, chronology, API costs, and failures. Models propose facts and events; deterministic Python decides which changes can be applied.

For a quick technical review, start with [the model API integration and prompts](src/job_tracker/ai.py), [worker orchestration and spending controls](src/job_tracker/worker.py), and [the AI engineering walkthrough](docs/ai-engineering.md). The table below connects each skill to implemented behavior; the test suite and commit history provide evidence.

| Engineering area | Concrete implementation |
| --- | --- |
| AI integration | A two-stage pipeline uses GPT-6 Luna **Decisions** for relevance/event classification and GPT-5.4 mini **Responses** with a strict JSON schema for extraction. Pydantic validates fields and dates; evidence must be an exact excerpt from the supplied body. |
| Decision handling | Relevance below 0.1 skips extraction. Automatic updates require relevance and event confidence of at least 0.9 plus a clear identity. Otherwise a review item explains why a human decision is needed. Thresholds are defaults, not measured accuracy guarantees. |
| Application matching | Thread history and requisition IDs precede company/role matching. Weaker matches stay within the selected search. Conflicting IDs and multiple matches cannot silently merge records. |
| Persistence | SQLAlchemy models separate searches, accounts, messages, jobs, applications, events, tasks, scans, reviews, and usage. SQLite foreign keys/unique constraints protect relationships; Alembic upgrades preserve existing data. |
| Reliability | Durable jobs survive pauses/restarts. Cached classifications and extractions avoid repeating completed AI work. Normalized timestamps prevent older emails from overwriting newer status; manual status corrections are protected. |
| Desktop design | Qt Quick/QML handles presentation; separate import and snapshot workers, cached getters, throttled progress signals, and virtualized review cards keep the interface usable during imports. Record mutations remain disabled while a scan runs. |
| Credentials | Read-only OAuth, browser sign-in, Gmail PKCE, OS keyring storage, and memory-only sessions. Large OAuth caches are split into bounded entries to fit Windows credential-size limits, with rollback on failed writes. |
| Cost control | Reserve estimated usage before dispatch, settle reported tokens, and retain a durable usage ledger. History scans have explicit budgets; opt-in live processing has per-sync and daily limits. |
| Excel interoperability | Styled, filterable snapshots and validated dropdowns. External strings are written as text so email/company content cannot become spreadsheet formulas. |
| Delivery | Locked dependencies, Windows/Linux source checks, PyInstaller folder bundles, Inno Setup, frozen rendering/integrity checks, isolated installer lifecycle tests, release assets, and SHA-256 checksums through GitHub Actions. |

### What I learned and applied

- AI output needs typed validation, evidence, identity checks, and a human fallback. A confident label alone is insufficient to merge applications safely.
- Prompt engineering includes deciding what a model should abstain from, defining an output contract, and enforcing that contract in application code. Model confidence and schema compliance are different from measured correctness.
- Model routing is a product decision: use a decision endpoint for bounded labels and a generation endpoint for extracted objects, then skip work that is not needed.
- Event history and current state serve different purposes: preserve evidence while projecting the latest valid status and protecting manual corrections.
- Local-first storage supports offline use, but credentials, backups, migrations, and uninstall behavior still require deliberate handling.
- Recovery and cost control belong together: caching completed work and retaining request reservations matter as much as successful classification.
- A working source app is only part of delivery. Frozen Qt dependencies, Windows DLL discovery, installer lifecycle, provider policies, and real-account validation need separate checks.

Read [the architecture](docs/architecture.md), or start with [`ai.py`](src/job_tracker/ai.py), [`worker.py`](src/job_tracker/worker.py), [`services.py`](src/job_tracker/services.py), and [`ui/bridge.py`](src/job_tracker/ui/bridge.py). The commit history groups coherent features and fixes incrementally.

## Technology and processing flow

| Layer | Stack |
| --- | --- |
| Desktop | Python 3.13, PySide6, Qt Quick/QML, Qt Basic controls |
| Database | SQLite with WAL/foreign keys, SQLAlchemy 2, Alembic |
| Validation / HTTP | Pydantic 2, httpx, OpenAI Python SDK 3.26+ (Decisions support) |
| Sign-in | google-auth-oauthlib, MSAL public client, OS keyring |
| Excel | openpyxl |
| Development / delivery | uv lockfile, Ruff, pytest/pytest-qt, PyInstaller, Inno Setup, GitHub Actions |

```mermaid
flowchart LR
    Mail[Gmail / Microsoft Graph] -->|read-only OAuth| Worker[Python background worker]
    Worker --> Classify[OpenAI Decisions: relevance + event]
    Classify --> Extract[OpenAI Responses: structured extraction]
    Extract --> Validate[Pydantic + evidence + identity checks]
    Validate --> DB[(Local SQLite)]
    Validate --> Review[Human review]
    Review --> DB
    DB --> UI[PySide6 / QML dashboard]
    DB --> Excel[Excel snapshot]
```

## Run on Windows

**v0.2.1 · Self-configured edition** — Windows x64, with user-owned email OAuth and OpenAI credentials.

- [Download the Windows installer](https://github.com/khalifehbasiri/Job-Tracker-AI/releases/latest/download/Job-Tracker-AI-Setup.exe).
- [Download the portable ZIP](https://github.com/khalifehbasiri/Job-Tracker-AI/releases/latest/download/Job-Tracker-AI-Windows-x64.zip).
- [Download the standalone HTML setup guide](https://github.com/khalifehbasiri/Job-Tracker-AI/releases/latest/download/Job-Tracker-AI-Setup-Guide.html), then open it in your browser.
- [Release notes and all assets](https://github.com/khalifehbasiri/Job-Tracker-AI/releases/latest), including SHA-256 checksums and matching dependency sources.

Builds are unsigned and require your own credentials. Shared project-owned sign-in is not included. Decisions is a provider public-beta dependency. Review the [release checklist](docs/release-checklist.md) and [setup guide](docs/mailbox-setup.md) for account requirements and validation limits.

The installer provides Start menu and optional desktop shortcuts. For the ZIP, extract the entire folder and run `Job-Tracker-AI.exe`; keep `_internal` alongside it. Neither download requires a separate Python installation. Installer upgrades and uninstallation preserve the user database; uninstalling does not erase records or OS credentials.

**Read the HTML setup guide:** click **Help & setup guide** from any page or press **F1**. It opens in your default browser and works offline. The Windows installer also adds a setup-guide Start menu shortcut. You can open `Setup guide/setup.html` directly from the installed or portable app folder. The file path on the developer's computer is not needed.

Maintainers can build the downloads with `uv sync --locked --group build`, install Inno Setup 6, and run `uv run python scripts/build_windows.py --installer`. Building requires internet access to fetch checksum-verified matching dependency sources. The [Windows release workflow](https://github.com/khalifehbasiri/Job-Tracker-AI/actions/workflows/windows-release.yml) validates the frozen app, cross-version upgrades, shortcuts, and preserved records, then uploads artifacts. A matching version tag creates a draft release; publication happens only after validation.

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
uv run job-tracker --demo --theme dark
```

For your own records, create a search and add applications or import your existing `.xlsx` workbook from Applications. Manual tracking works without an API key or email connection.

To enable email processing, follow the welcome wizard or configure your own OAuth registration in Settings, connect a mailbox, save your OpenAI key, and preview a scan in Email history. Automatic processing is disabled until you explicitly enable it. The first mailbox connection starts from the present; use a historical scan to reconstruct older applications.

## First use and tracking rules

1. Name a search in the welcome wizard. To rename it or change dates/archive state later, open Settings → Current job search → Edit search. Search dates are labels, not restrictions on scans.
2. Create an OpenAI project key and configure API billing, then Save key → Check key in Settings. Check key reads extraction-model metadata without inference; it does not prove Decisions availability or working inference billing.
3. For Gmail, enable Gmail API in Google Cloud, configure External consent in Testing, add your address as a test user and add `gmail.readonly`. Create a Desktop app OAuth client, download its JSON outside Git, and import it through Configure your OAuth app before Connect Gmail.
4. For Outlook, register an Entra app supporting organizational and personal accounts. Configure Mobile and desktop → `http://localhost`, plus delegated Graph `Mail.Read` and `User.Read`. Save the Application (client) ID through Configure your OAuth app before Connect Outlook. No client secret is needed.
5. Select Gmail, Outlook, or all mailboxes, then preview a date range in Email history and set a USD limit. Connecting alone does not start processing. The [complete setup guide](docs/mailbox-setup.md) includes every registration step and troubleshooting detail; click the information indicator beside setup for a summary.
6. Expand uncertain emails in Review inbox to link, create, or ignore a record. Search includes the full email body. An overlapping scan can resolve older clear “no exact match” reviews using their cached classification/extraction without another AI call; uncertain reviews remain available for explicit resolution.
7. Export from Applications or Settings. Opt into automatic processing only when ready. Close the app window to stop processing and discard session-only credentials.

**Date applied:** only an application-confirmation email can fill a blank date. Use an explicitly extracted application date when present, otherwise the email's received date in UTC. This fallback is the confirmation date and can differ from the form-submission date. Existing dates are preserved; rejection/interview emails never invent an applied date. On upgrade, blank dates with existing saved confirmation events are repaired locally without API calls.

**Unmatched updates:** a clear, confident rejection/assessment/interview/offer with company and role creates a record at that status. An unmatched rejection is `Applied / Rejected` with an unknown applied date. Conflicting identities, multiple matches, missing fields, and uncertain classifications remain in review. Older confirmations cannot undo a later rejection.

**Import removal:** Remove hides the history entry and makes it unavailable for Resume. Pause a running scan first. Applications, saved emails, reviews, and usage records remain. Completed imports have no Resume button. A new overlapping scan can reuse cached results.

**Excel edits:** dropdowns edit the exported snapshot, not SQLite. Re-importing adds missing records and skips duplicates; it does not overwrite existing applications. Edit the app's record if you want later exports to reflect a change.

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

Tests use fake mailboxes/AI responses and isolated databases. They verify matching, chronology, review, budgets/retries, credential handling, migration preservation, Excel safety/dropdowns, and QML behavior. They do not establish real-provider availability or classifier accuracy. Reproduce the fictional README images with `uv run python scripts/capture_demo.py`; regenerate the Windows icon with `uv run python scripts/build_icon.py`. The [logo design note](docs/logo-design.md) records the generated artwork and prompt.

Frozen smoke tests render the light dashboard and dark settings, validate SQLite and bundled assets, and reject unused Qt browser/virtual-keyboard/charts components. Run `uv run python scripts/test_installer.py` after building to validate isolated install, same-version upgrade, and uninstall with fictional records.

Release builds fail on unreviewed Qt runtime modules or missing library license texts. Matching Qt/PySide/certifi source archives are distributed alongside binaries, with upstream URLs and hashes. See [dependency notices and replacement instructions](packaging/third-party-notices.md). Model/API availability and real-account behavior still depend on the user's project, provider, and tenant policies. There is no measured classifier-accuracy claim. Code signing, model/pricing controls, retention/erasure UI, a disclosed paid fictional-data AI test, and project-owned OAuth onboarding remain future milestones rather than advertised features of this release.

## Troubleshooting

| Symptom | First check |
| --- | --- |
| Gmail blocked | Correct project, Gmail API enabled, Desktop client type, Testing test-user address, and read-only scope. |
| Outlook `unauthorized_client` | Correct Application (client) ID, personal-account support saved, localhost desktop redirect, and delegated permissions. |
| Browser finished but app disconnected | The callback is not proof of successful mailbox access/token storage. Read provider status in Settings, check permissions, and try Session only. |
| OpenAI check fails | Key/project permissions, extraction-model access, and API billing. A metadata check does not verify Decisions or inference availability. |
| No records after a scan | Correct search/provider, paused or failed status, and Review inbox. Some messages are unrelated or lack enough identity information. |
| Automatic processing idle | Enabled setting applied, connected selected source, key present, unarchived search, budgets available, and no visible unfinished import waiting for attention. |
| Excel changes missing in a new export | Exports are snapshots. Edit the record in the app; duplicate imports do not overwrite it. |
| Source changes not visible | Close the existing app window (or use Quit in the tray menu for older versions) and start the updated app. |

## License

Application code is [MIT licensed](LICENSE). Dependencies retain their own licenses. PySide6/Qt distributions have LGPL/GPL or commercial terms; binary releases must preserve applicable dependency notices and comply with those terms.
