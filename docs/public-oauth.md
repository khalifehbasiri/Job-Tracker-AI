# Future project-owned public sign-in

The current development preview requires each user to configure their own email OAuth registration and OpenAI key. No project-owned client ID or Google OAuth JSON is used or shipped. Existing locally configured registrations and connected accounts are preserved. Follow [the complete setup guide](mailbox-setup.md).

Shared Connect Gmail / Connect Outlook onboarding is a future milestone. It is separate from publishing open-source code or a preview download. Bringing your own registration does not waive provider policies.

## Google launch work

1. Keep a separate production project with Gmail API enabled and an External audience.
2. Host a public app homepage and privacy policy on a domain the owner can verify in Google Search Console. A GitHub repository does not establish ownership of github.com. Link the source repository from that site.
3. Complete Branding, domain ownership verification, and approved branding publication.
4. Declare only `https://www.googleapis.com/auth/gmail.readonly`. Explain why email bodies are needed to distinguish job applications from ads and extract company, role, status, and explicit deadlines.
5. Submit restricted-scope verification with a demonstration of consent, mailbox access, authorized processing, review, and data removal.
6. Disclose transmission of selected email text to OpenAI. This is a third-party server transfer even with local SQLite and user-owned API keys. Plan for applicable independent security assessment and annual renewal; do not claim an entirely-local exemption.
7. Implement and validate the required retention, erasure, and security controls. The current SQLite database is unencrypted and account-history erasure is not yet exposed in the UI.
8. Configure the production audience for launch. Publishing alone does not remove verification requirements, warnings, or caps.

Sources: [brand/domain requirements](https://developers.google.com/identity/protocols/oauth2/production-readiness/brand-verification), [restricted-scope requirements](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification).

## Microsoft launch work

1. Configure organizational-plus-personal supported accounts, the Mobile/Desktop `http://localhost` redirect, and delegated Mail.Read/User.Read.
2. Complete branding, homepage, privacy policy, and support information.
3. Test personal Outlook and accounts in a separate work/school tenant. Organization consent policies may require administrator approval.
4. Pursue publisher verification for broader organizational adoption. It requires the appropriate verified Microsoft AI Cloud Partner Program organizational identity, tenant, and domain. Verification is not a universal prerequisite for personal Outlook access and does not override workplace consent policies.

Sources: [desktop configuration](https://learn.microsoft.com/en-us/entra/identity-platform/scenario-desktop-app-configuration), [publisher verification](https://learn.microsoft.com/en-us/entra/identity-platform/publisher-verification-overview).

## Credentials and future builds

The original Google JSON stays outside Git. Native Desktop client metadata is extractable from distributed applications and cannot act as a protected backend secret. Future builds must never bundle user tokens, OpenAI keys, service-account keys, or confidential Web-client secrets. Store user credentials in the OS credential store or memory and use PKCE.

This preview no longer reads or packages the formerly generated Google build file. Its GitHub Actions workflow does not consume the earlier OAuth repository secret. Provider approvals cannot be completed through application code.
