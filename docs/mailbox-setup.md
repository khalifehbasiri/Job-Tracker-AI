# Development preview: complete setup guide

Email onboarding is still in development. **This release requires your own OpenAI API key and your own email OAuth registration.** No shared project credentials are included. Manual tracking and Excel import/export need no credentials. An email password, Microsoft client ID, and OpenAI API key are different things.

This guide is also available offline from Settings and the welcome wizard. Provider consoles can change labels; official references are linked below.

## 1. Start the app

1. Unzip the entire portable download, then run `Job-Tracker-AI.exe`. Keep it alongside `_internal`. Alternatively, run the Windows installer. Source users should follow the README.
2. In the first-run wizard, name your search (for example `2026 Co-op`) and click Next. Create additional searches later using New search.
3. Choose Gmail or Outlook. You only need to register the provider you plan to use.
4. Next can skip email/AI steps. Set up later opens manual tracking. Reopen the wizard from Settings.

## 2. Create your OpenAI API key

1. Sign in or create an account at [OpenAI Platform](https://platform.openai.com/).
2. Select your organization and a project. A dedicated project helps attribute this app's usage.
3. Open Billing and configure API billing/credits as offered for your account. ChatGPT subscriptions do not include API credits.
4. Open [API keys](https://platform.openai.com/api-keys) for the selected project. Choose Create new secret key, name it `Job Tracker AI`, and create it. Ask your organization administrator if key creation is restricted.
5. Copy the displayed secret and keep it private. Do not paste it into GitHub, issues, screenshots, or email. If lost, create a replacement and revoke the old key.
6. In the wizard or Settings → AI configuration, paste it into the masked field and click Save key. Session only keeps it in memory until Quit; otherwise the OS credential store protects it.
7. Click Check key. This checks extraction-model metadata without processing email or generating output. It does not confirm Decisions access or available billing credit.
8. Review provider billing/usage and set app per-sync, daily, and historical-scan spending limits before processing.

References: [OpenAI quickstart](https://developers.openai.com/api/docs/quickstart), [project administration](https://developers.openai.com/api/docs/guides/production-best-practices).

This preview uses GPT-6 Luna through Decisions and GPT-5.4 mini for extraction. Availability depends on your project. There is no silent model substitution. The separate paid fictional-email test from the roadmap is not implemented yet.

## 3A. Set up Gmail

1. Open [Google Cloud Console](https://console.cloud.google.com/) using the Google account that will own the registration.
2. Project selector → New project. Name it `Job Tracker AI Personal`, create it, and select it.
3. APIs & Services → Library → Gmail API → Enable.
4. Google Auth platform → Branding → Get started, if prompted. Enter an app name, support email, and developer contact email. Choose External for personal Gmail and complete setup.
5. Audience → keep Testing → Test users → Add users. Add the exact Gmail address you will connect, including when it is the project owner.
6. Clients → Create client → Desktop app. Name it `Job Tracker AI Windows`, create it, and download its JSON outside this repository, for example `Documents/JobTrackerAI-OAuth/google-desktop-client.json`.

References: [Google API/client setup](https://developers.google.com/workspace/gmail/api/quickstart/python), [consent configuration](https://developers.google.com/workspace/guides/configure-oauth-consent).

7. Data Access → Add or remove scopes. Add exactly `https://www.googleapis.com/auth/gmail.readonly` and save. No send/delete scope is needed. [Gmail scope reference](https://developers.google.com/workspace/gmail/api/auth/scopes)
8. In the wizard or Settings → Configure your OAuth app, choose Import/Choose Google Desktop JSON and select that file. Use the downloaded Desktop (`installed`) JSON, not a Web client or service-account key.
9. Select Session only if desired, then Connect Gmail. Read the disclosure and continue to the browser. Sign in with your listed test account and consent to read-only access.
10. Return to the app and wait for your address to appear as connected. Browser callback success alone does not confirm credential storage or mailbox access.

Desktop sign-in uses PKCE and a random-port loopback callback; no hosted callback website is needed for this Desktop registration. Keep the downloaded file outside Git. Desktop registration metadata cannot act as a confidential backend secret; user tokens and API keys must remain private. [Desktop OAuth](https://developers.google.com/identity/protocols/oauth2/native-app)

Testing restricts users and can cause authorization expiry, requiring reconnection. Your own registration is not a blanket exemption from Google's policies. Public restricted-scope access and sending Gmail text to OpenAI can require verification and security assessment. This preview does not claim production approval. [Google requirements](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification)

## 3B. Set up Outlook/Microsoft 365

1. Sign in at [Microsoft Entra admin center](https://entra.microsoft.com/) and select your directory. You need an Entra tenant and app-registration permission. If unavailable, follow Microsoft's prerequisites or ask your organization administrator.
2. Entra ID → App registrations → New registration. Name it `Job Tracker AI Personal`.
3. Supported account types → Accounts in any organizational directory and personal Microsoft accounts (also labelled Any Entra ID Tenant + Personal Microsoft accounts). This matches the app's common authority.
4. Register. On Overview, copy Application (client) ID. Do not use Object ID or Directory (tenant) ID.

Reference: [Microsoft registration/prerequisites](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app).

5. Authentication → Add a platform → Mobile and desktop applications → add `http://localhost` and save. The preview interface may say Add Redirect URI instead. Confirm supported account types are saved.
6. Do not create a client secret. This app uses interactive browser sign-in with PKCE, not a confidential Web client or a device-code flow. [Desktop configuration](https://learn.microsoft.com/en-us/entra/identity-platform/scenario-desktop-app-configuration)
7. API permissions → Add a permission → Microsoft Graph → Delegated permissions. Add Mail.Read and retain/add User.Read. Do not select Application permissions or Mail.ReadWrite. An organization may require administrator consent. [Graph permissions](https://learn.microsoft.com/en-us/graph/permissions-reference)
8. In the wizard or Settings → Configure your OAuth app, paste Application (client) ID and click Save Microsoft client ID.
9. Choose Outlook in the email-source selector. Click Connect Outlook, read the disclosure, and sign in through your browser using an account with an Outlook/Exchange mailbox.
10. Return to the app and wait for the connected address. If secure storage fails, try Session only. Successful browser authentication can still be followed by failed mailbox access or storage.

Microsoft has no Google-style Testing/Production switch. Work/school organizations can restrict consent to unverified publishers; personal Outlook success does not guarantee workplace access. [Publisher verification](https://learn.microsoft.com/en-us/entra/identity-platform/publisher-verification-overview)

## 4. Select a provider and import

1. In Settings or Email history, choose Gmail, Outlook, or All mailboxes. The choice persists and controls new history previews and automatic processing. Other accounts remain saved; existing job records remain visible.
2. Select the target job search. Connecting email alone makes no AI requests.
3. Email history → choose 1, 3, 6, or 12 months or custom dates → Preview scan. Dates are inclusive in UTC and processing is oldest first. Preview accesses mailbox metadata but makes no AI calls.
4. Review message count, illustrative cost, and privacy disclosure. Enter a USD spending limit and confirm to start. Actual provider charges can differ from app estimates.
5. Check Review inbox for uncertain results and Applications for confirmed records. Pause keeps completed work. Resume uses the original scan's mailboxes even after changing the provider selector.
6. Optionally enable automatic processing in Settings and apply per-sync/daily limits. The app checks every five minutes while running and awake. Paused scans require attention before polling continues.
7. Export the selected search to Excel. Export/import/manual editing have no API cost.

## 5. Troubleshooting and removing access

- Google blocked: check your project, test-user address, Gmail API, Desktop client type, and read-only scope. A different project's JSON may not permit your account.
- Outlook unauthorized_client: check Application client ID and personal-account support. Admin approval required: contact the mailbox's administrator.
- Browser finished but app not connected: read the provider-specific status in Settings. Check mailbox permissions and secure storage, try Session only, and close stale browser sign-in tabs before retrying.
- OpenAI 401: replace the key. 403/404: check project permissions and endpoint/model access. 429: check API billing, credits, and rate limits. Check key success does not establish Decisions access.
- Automatic processing idle: check the selected source, connected mailbox, saved key, enabled processing, archived search, budgets, and paused scans.
- Reconnect after configuring the registration. Disconnect removes the account's local tokens but retains job/email history. Revoke provider consent in Google/Microsoft account settings for provider-side removal.
- Remove the OpenAI key using Remove in Settings, and revoke it in OpenAI Platform if necessary.
- Closing the window can keep the worker in the tray. Quit from the tray stops processing and discards session-only credentials.

## Local storage and known limitations

SQLite contains normalized email text and job history and is not encrypted by the app. Its path is shown in Settings, outside the installation directory. Keep backups private. Uninstall preserves the database and OS credentials; removing the program is not erasing your data.

Full account-history erasure/retention controls, signed releases, broad real-account validation, and project-owned public OAuth onboarding remain in development. Using your own OAuth registration does not waive provider policies. See PRIVACY.md and the release checklist in the repository.
