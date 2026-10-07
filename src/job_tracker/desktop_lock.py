"""One desktop worker per database prevents duplicate requests and competing budgets."""

from pathlib import Path

from PySide6.QtCore import QLockFile


def acquire_database_lock(path: Path) -> QLockFile:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(path) + ".lock")
    lock.setStaleLockTime(0)  # Qt still detects locks whose local owner process has exited.
    if not lock.tryLock(0):
        if lock.error() != QLockFile.LockFailedError:
            raise ValueError("Cannot open this database folder. Check its access permissions.")
        raise ValueError("This database is already open. Use the existing Job Tracker window.")
    return lock
