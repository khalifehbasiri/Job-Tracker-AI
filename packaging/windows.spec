# Build from the repository root with: python -m PyInstaller packaging/windows.spec
from pathlib import Path

root = Path(SPECPATH).parent
data = [
    (str(root / 'src/job_tracker/ui'), 'job_tracker/ui'),
    (str(root / 'src/job_tracker/assets'), 'job_tracker/assets'),
    (str(root / 'src/job_tracker/migrations'), 'job_tracker/migrations'),
    (str(root / 'src/job_tracker/help'), 'job_tracker/help'),
    (str(root / 'build/notices'), 'THIRD_PARTY_NOTICES'),
    (str(root / 'LICENSE'), '.'),
    (str(root / 'PRIVACY.md'), '.'),
]
a = Analysis(
    [str(root / 'scripts/desktop_entry.py')],
    pathex=[str(root / 'src')],
    binaries=[], datas=data,
    hiddenimports=['keyring.backends.Windows', 'sqlalchemy.dialects.sqlite',
                   'alembic', 'alembic.runtime.migration', 'google.auth.transport.requests'],
    hookspath=[str(root / 'packaging/hooks')], hooksconfig={}, runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
              'PySide6.QtWebEngineQuick', 'tkinter', 'pytest'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Job-Tracker-AI',
          icon=str(root / 'src/job_tracker/assets/logo.ico'),
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Job-Tracker-AI')
