"""Use native desktop input; the optional virtual keyboard is not used by this app."""

from pathlib import Path

from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = [
    entry for entry in binaries if Path(entry[0]).name.lower() != "qtvirtualkeyboardplugin.dll"
]
