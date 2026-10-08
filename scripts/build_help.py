"""Generate the bundled offline guide from the reviewable Markdown source."""

from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]


def main():
    body = markdown.markdown(
        (ROOT / "docs/mailbox-setup.md").read_text(encoding="utf-8-sig"),
        extensions=["sane_lists"],
    )
    path = ROOT / "src/job_tracker/help/setup.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Job Tracker AI setup</title><style>"
        "body{font:16px/1.65 system-ui,sans-serif;max-width:900px;margin:40px auto;"
        "padding:0 24px;background:#f4f6f1;color:#20362e}a{color:#216e62}"
        "code{overflow-wrap:anywhere}li{margin:8px 0}h2{margin-top:40px}"
        "</style><main>" + body + "</main></html>\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
