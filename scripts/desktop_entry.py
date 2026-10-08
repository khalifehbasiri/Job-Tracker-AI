"""Frozen desktop entry point (the same application used by the source command)."""

from job_tracker.main import main

if __name__ == "__main__":
    raise SystemExit(main())
