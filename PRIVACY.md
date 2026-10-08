# Privacy and local data

Job Tracker AI has no developer-operated server, telemetry, advertising, or cloud database. The application connects directly to Google or Microsoft for email and to OpenAI for AI processing. These providers apply their own privacy and retention policies.

## What is stored

SQLite stores searches, applications, event history, tasks, mailbox addresses, provider message IDs, normalized sender/subject/body text, AI results, review items, scan checkpoints, and a usage ledger. The database lives in the OS application-data directory by default. Settings displays its location. It is not encrypted by this application.

Public downloads do not contain a database, application records, connected mailboxes,
API keys, or OAuth client JSON. A normal first launch creates an empty search and
opens setup. Demonstration records are created only with the explicit `--demo`
command-line option; README screenshots use fictional data. Source and installed
builds use the same local data directory and credential service for a given OS
user. Installing an update or reinstalling therefore preserves that user's
previous records and connections; those records did not arrive in the download.

API keys and OAuth token caches are stored separately in a supported OS credential store. Session-only credentials remain in process memory. Replacing a saved API key with a session-only key removes the previous saved key when secure storage is available. Credentials are excluded from database backups and workbook exports. This development preview requires user-owned OAuth registrations and does not bundle project-owned registrations. Original Google JSON stays outside the repository; imported Google configuration uses the credential store or session memory. Microsoft client IDs are public registration identifiers saved in local settings.

Large credentials may occupy several encrypted entries in the OS credential store to fit its size limits. Their small manifest contains only assembly metadata, and all pieces remain in the credential store. Disconnecting removes the associated manifest and pieces. The app does not fall back to plaintext token files.

## Email access and AI transmission

Mailbox permissions are read-only. The app does not send, delete, or mark messages as read. It reads message IDs and, when processing a scan, the sender, subject, timestamps, thread identity, and body. It skips Gmail attachments and never follows email links or executes attachment content. Normalization strips HTML/script markup and common quoted reply chains, then limits body length.

A historical preview lists message IDs and computes an estimate without calling OpenAI. The scan reads received-date metadata as necessary to process mail oldest first. Starting the scan authorizes sending message text for classification, including messages that ultimately prove unrelated to applications. Relevant or uncertain messages also undergo extraction. Automatic AI processing is opt-in and makes the same transmissions for new messages. Normalization is not anonymization; message text can include personal information. Connecting a mailbox alone does not start AI processing.

Job Tracker AI's use and transfer of information received from Google APIs will adhere to the [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy), including its Limited Use requirements. Email data is used only for the user-visible job tracking features, is not sold or used for advertising, and is not used by this app to train AI models. The app developer does not receive user email data. Users should keep optional OpenAI project data sharing/model-training settings disabled for projects processing Gmail data.

Extraction requests set `store=false`. This does not promise zero provider retention. Consult [OpenAI's API data controls](https://developers.openai.com/api/docs/guides/your-data), [Google's privacy policy](https://policies.google.com/privacy), and [Microsoft's privacy statement](https://privacy.microsoft.com/privacystatement).

## Backups, deletion, and reports

Excel exports include application records and event evidence excerpts, not full mailbox bodies. SQLite backups include the saved message text. Keep both private. An archived search still exists in the database.

Disconnecting a mailbox removes its locally stored credentials and preserves records. Removing the API key prevents subsequent AI scans; pause a running scan before changing credentials. Revoke application consent in your provider account settings to revoke provider access. To erase local records, quit the application and delete the database and its associated WAL/SHM files; also remove any backups, exports, and demo database you no longer want. There is no in-app account-wide erase feature in this release.

Never include real emails, API keys, tokens, databases, or private workbooks in public GitHub issues. Use fictional or redacted examples.
