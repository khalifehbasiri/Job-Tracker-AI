"""Keep the QML modules this app uses, rather than every optional Qt add-on."""

from pathlib import PurePath

from PyInstaller.utils.hooks.qt import add_qt6_dependencies, pyside6_library_info

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
# Production builds do not expose or distribute optional QML debugger/profiler plugins.
binaries = [entry for entry in binaries if "qmltooling" not in PurePath(entry[0]).parts]
qml_binaries, qml_datas = pyside6_library_info.collect_qtqml_files()
allowed = {
    "QtQml",
    "QtQml/Models",
    "QtQml/WorkerScript",
    "QtQuick",
    "QtQuick/Window",
    "QtQuick/Layouts",
    "QtQuick/Templates",
    "QtQuick/Controls",
    "QtQuick/Controls/impl",
    "QtQuick/Controls/Basic",
}


def used(entry):
    destination = PurePath(entry[1]).as_posix().split("/qml/", 1)[-1]
    return destination in allowed or destination.startswith("QtQuick/Controls/Basic/")


binaries += [entry for entry in qml_binaries if used(entry)]
datas += [entry for entry in qml_datas if used(entry)]
