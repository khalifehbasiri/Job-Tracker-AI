# Job Tracker AI development preview

Windows x64 downloads need no Python installation:

- **Job-Tracker-AI-Setup.exe**: per-user installer with shortcuts and uninstall support.
- **Job-Tracker-AI-Windows-x64.zip**: unzip the whole folder, then run Job-Tracker-AI.exe.
- **SHA256SUMS.txt**: checksums for both downloads.

This unsigned development preview requires your own OpenAI API key and Google
Desktop OAuth registration or Microsoft Application client ID. Email setup and
broad provider compatibility are still being validated. The welcome wizard and
offline setup guide explain every registration step.

Choose Gmail, Outlook, or all mailboxes for new history scans and automatic
processing. Existing job records remain visible. Automatic processing is off by
default; connecting email does not start AI processing.

Historical imports now keep navigation, local search, review expansion, and Pause
responsive. Database refreshes and timelines run in a separate background worker;
progress no longer rebuilds the entire interface. Interrupted imports offer
Resume after restarting, preserving completed records and recorded usage.

AI sends selected email text to OpenAI and uses your API credits. Manual tracking
and Excel import/export have no API costs. Records stay in local, unencrypted
SQLite. Uninstalling preserves the database and OS credentials.

Quit from the tray before upgrading. Back up your database in Settings before
trying a preview. See README, docs/mailbox-setup.md, PRIVACY.md, and
docs/release-checklist.md for limitations and validation status.
