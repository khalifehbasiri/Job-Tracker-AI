"""Frozen desktop entry point (the same application used by the source command)."""

import sys
import traceback
from pathlib import Path

if __name__ == "__main__":
    try:
        from job_tracker.main import main

        raise SystemExit(main())
    except Exception:
        # Frozen windowed programs have no stderr. Only fictional smoke mode writes a log.
        if "--demo" in sys.argv and "--screenshot" in sys.argv:
            screenshot = Path(sys.argv[sys.argv.index("--screenshot") + 1])
            with screenshot.with_suffix(".error.txt").open("w", encoding="utf-8") as output:
                traceback.print_exc(file=output)
            raise SystemExit(1) from None
        raise
