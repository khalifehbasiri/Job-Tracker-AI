# Public mailbox sign-in

The app now uses maintained desktop OAuth registrations for ordinary Connect Gmail / Connect Outlook buttons. Users provide their own OpenAI API key, but do not need to register their own email app when maintained clients are included. Advanced OAuth setup supports forks and development. **Wiring the clients does not establish Google verification or Microsoft publisher verification.** Both remain release gates until the owner completes the provider processes.

## Registration metadata and private user credentials

The Microsoft application client ID is public and included in source. Google Desktop client metadata is read from an ignored generated `src/job_tracker/google_desktop_oauth.json` file. The original downloaded JSON stays outside the repo. GitHub Actions receives it from the encrypted repository secret `GOOGLE_DESKTOP_OAUTH_JSON` and generates a sanitized native-client configuration for the build. Logs never print values. Fork pull requests do not receive the repository secret.

The generated file includes only the installed client ID, native-client string, and fixed Google endpoints. It never includes user tokens, OpenAI keys, other client types, or extra JSON fields. It is included in distributed Python packages when supplied at build time. A desktop client cannot keep a client secret confidential once shipped; Google's native-client string identifies a public installed app, not a protected backend. Protect user access/refresh tokens in the OS credential store and use browser sign-in with PKCE. Never bundle a web-client secret or service-account key.

For a local build, run:

```powershell
uv run python scripts/configure_google_oauth.py --source "C:\private-folder\google-desktop-client.json"
uv build
```

Source checkouts without the generated configuration can use Advanced OAuth setup. Packaged builds with the maintained configuration open Google sign-in directly. A test-user restriction is controlled by Google, not by this configuration file.

## Google owner steps

1. In Google Auth Platform, select the Cloud project for the maintained Desktop client. Keep Gmail API enabled and the audience External. Use a separate project/client for development if continuing tests.
2. In Branding, supply Job Tracker AI's name, a support email, and developer contact details. The project repository is the source/support homepage: <https://github.com/khalifehbasiri/Job-Tracker-AI>. The privacy policy is linked from its README.
3. Before public brand verification, provide a publicly accessible app homepage and privacy policy on an authorized domain whose ownership the project owner can verify in Google Search Console. A repository on `github.com` does not give the project owner control of that domain. A maintained site can link back to the GitHub repo; do not claim ownership of `github.com` or bypass Google's review. Host the privacy policy on the same site domain and link it from the homepage.
4. In Data Access, declare only `https://www.googleapis.com/auth/gmail.readonly`. The app reads sender, subject, body, timestamp, and thread identity to recognize application acknowledgments and follow-up events. Metadata-only permission cannot supply the body required for extraction.
5. Complete Branding verification, publish approved branding, and use Verification Center to submit restricted-scope access. Record a demonstration of consent, read-only connection, explicit scan authorization, spending preview, oldest-first processing, review, export, and credential removal. Use consenting demonstration accounts and keep private emails out of public recordings.
6. Declare that selected email text is sent directly from the user's desktop to OpenAI for classification and extraction. This is a third-party server transfer even though SQLite is local and the user supplies the API key. Plan for Google's required independent security assessment and annual renewal; do not claim the app qualifies for the entirely-local exemption.
7. Address the reviewer's requirements, including retention/deletion and security controls, before public launch. The current database is unencrypted and account-wide data erasure is not yet exposed in the UI; these are recorded in the privacy policy and roadmap.
8. Move the production audience out of Testing when ready for launch and approved access. Publishing alone does not remove the restricted-scope verification requirement, unverified-app warnings, or user caps. Test-mode Gmail refresh tokens can expire after seven days for the requested scopes.

Scope justification for the submission: “Job Tracker AI is a desktop productivity and reporting application. It reads the user's email to recognize job applications and subsequent assessments, interviews, offers, and rejections, then maintains application records and timelines visible in the user's local dashboard. It needs email bodies to distinguish application acknowledgments from job advertisements and extract company, role, requisition, and explicit deadlines. It does not send or modify email, read attachments, or use email data for advertising or model training.”

## Microsoft owner steps

1. Use the maintained application registration, with supported accounts set to **Any Entra ID Tenant + Personal Microsoft accounts**.
2. Under Authentication, add the Mobile and desktop platform with `http://localhost`. The Python app uses an interactive public-client flow. Do not create or distribute a confidential client secret.
3. Add Microsoft Graph **Delegated** permissions `Mail.Read` and `User.Read`. Do not add application-wide permissions or `Mail.ReadWrite`.
4. Set branding, support/homepage and privacy-policy links. Use the GitHub repository and its privacy policy for current project information; configure a verified publisher domain if pursuing publisher verification.
5. Follow Microsoft's publisher-verification process with the appropriate verified Microsoft AI Cloud Partner Program account and tenant/domain configuration. The project owner must supply the required organizational identity; source code cannot obtain verification automatically.
6. Test with a personal Outlook mailbox and a separate work/school tenant. Organizations can require administrator approval even with delegated read-only permissions. The app verifies both profile and mailbox access before showing an account as connected and retains a safe error in Settings if sign-in fails.

## Official references

- [Google Gmail scopes](https://developers.google.com/workspace/gmail/api/auth/scopes)
- [Google brand verification and domain requirements](https://developers.google.com/identity/protocols/oauth2/production-readiness/brand-verification)
- [Restricted-scope verification and security assessments](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification)
- [Google Workspace user data and Limited Use policy](https://developers.google.com/workspace/workspace-api-user-data-developer-policy)
- [Google OAuth for desktop apps](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Microsoft desktop app configuration](https://learn.microsoft.com/en-us/entra/identity-platform/scenario-desktop-app-configuration)
- [Microsoft publisher verification](https://learn.microsoft.com/en-us/entra/identity-platform/mark-app-as-publisher-verified)
