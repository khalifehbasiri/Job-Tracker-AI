# Job Tracker AI

A Windows-first, open-source desktop app for tracking job applications across separate job searches. Records live in a local SQLite database. AI email processing is optional and uses your own OpenAI API key.

## Development

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
uv sync
uv run job-tracker
```

```sh
uv run ruff check .
uv run pytest
```

The initial application is under active development. See [the architecture](docs/architecture.md) for scope and decisions.

## Privacy

No developer API key, email content, workbook, or personal database is included in this repository. Credentials belong in the OS credential store. AI processing sends selected email text to OpenAI only after the user enables it. Local records and Excel exports work without AI.

## License

Application code is MIT licensed. Dependencies retain their own licenses. PySide6/Qt distributions have LGPL/GPL or commercial terms; preserve applicable dependency notices when redistributing binaries.
