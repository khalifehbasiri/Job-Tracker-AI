"""Generate the bundled offline guide from the reviewable Markdown source."""

from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]


def main():
    body = markdown.markdown(
        (ROOT / "docs/mailbox-setup.md").read_text(encoding="utf-8-sig"),
        extensions=["sane_lists", "toc"],
    )
    path = ROOT / "src/job_tracker/help/setup.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Job Tracker AI setup</title><style>"
        ":root{color-scheme:light dark;--bg:#f4f6f1;--fg:#20362e;--link:#216e62}"
        "body{font:16px/1.65 system-ui,sans-serif;max-width:900px;margin:40px auto;"
        "padding:0 24px;background:var(--bg);color:var(--fg)}a{color:var(--link)}"
        "pre{white-space:pre-wrap}code{overflow-wrap:anywhere}li{margin:8px 0}"
        "h2{margin-top:40px;scroll-margin-top:24px}nav{margin-bottom:24px}"
        "@media(prefers-color-scheme:dark){:root{--bg:#12201d;--fg:#e3ece6;--link:#91d1bd}}"
        "@media print{body{margin:0;background:white;color:black}nav{display:none}}"
        '</style></head><body><nav aria-label="Project links">'
        '<a href="https://github.com/khalifehbasiri/Job-Tracker-AI">Project &amp; downloads</a>'
        ' · <a href="https://github.com/khalifehbasiri/Job-Tracker-AI/blob/main/PRIVACY.md">Privacy</a>'
        "</nav><main>" + body + "</main></body></html>\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
