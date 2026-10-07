# Connecting a mailbox (developer release)

The tracker uses read-only OAuth. You enter email credentials in your provider's browser sign-in page, never in this app. No mailbox requests occur until you connect an account. AI imports require a separate OpenAI key and explicit authorization in the app.

This source release has no shared OAuth registration. Each developer supplies their own public installed-app registration. Turnkey public onboarding requires a maintained provider registration, privacy policy, and any required verification.

## Gmail

1. Create a Google Cloud project and enable the Gmail API.
2. Configure the OAuth consent screen. During development, add your account as a test user.
3. Create an OAuth client of type **Desktop app**, and download its client JSON outside the repository.
4. In Settings, choose **Connect Gmail** and select that JSON file.
5. Complete consent in your system browser. The app requests only `gmail.readonly`.

The loopback callback listens on `127.0.0.1` on a random port with PKCE. Tokens are stored in the OS credential store, or memory if you choose Session only. Testing-mode Google refresh tokens can expire; reconnect when prompted. Gmail read-only is a restricted scope; public release and sending Gmail-derived data to an AI provider require attention to Google's verification and user-data policies.

Sources: [installed-app OAuth](https://developers.google.com/identity/protocols/oauth2/native-app), [Gmail scopes](https://developers.google.com/workspace/gmail/api/auth/scopes), [verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification).

## Outlook / Microsoft 365

1. Register an application in Microsoft Entra that supports your intended account type (including personal Microsoft accounts when needed).
2. Add a **Mobile and desktop application** platform with `http://localhost` as a redirect URI.
3. Configure delegated Microsoft Graph permissions `Mail.Read` and `User.Read`. Do not create an application secret for this desktop client.
4. Paste its **Application (client) ID** in Settings and choose **Connect Outlook**.
5. Complete sign-in and consent in the system browser. Organization policies may require administrator consent.

The token cache is kept in the OS credential store or memory. Mailbox IDs request Microsoft's immutable-ID format so moving an email does not create a second processing identity.

Source: [MSAL token acquisition](https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens).

## AI configuration

Paste your OpenAI project API key in Settings. Use the Save, Test, and Remove buttons. Session only does not persist the new key. Test checks access to the extraction model; it does not send mailbox content or prove access to every endpoint. Decisions is currently a beta endpoint and must be available to your API account.

AI uses fixed model defaults in this release. Price constants were checked on 2026-10-07 and live in `ai.py`; update them when provider prices change. Usage shown in the app is an estimate/reservation ledger, not an account billing statement. Failed requests retain conservative reservations because their billed status may be unknown. A scan may pause early because a worst-case request reservation exceeds its remaining limit.

Automatic polling is opt-in, every five minutes. The first connection establishes a current checkpoint; use Email history for older mail. A paused scan needs manual attention before automatic polling continues for that search. Closing to tray continues processing while the computer is awake; explicit Quit stops it.

## Local data

The database contains normalized email text, extracted fields, and application history. It is not encrypted by this app. OS credential storage protects keys, not the whole database. Treat SQLite backups as private. Disconnecting removes locally saved OAuth credentials but retains application history; revoke provider consent in Google/Microsoft account settings if desired.
