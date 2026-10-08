# Dependency notices

This dynamically linked desktop distribution includes PySide6, Shiboken6, Qt,
and other open-source dependencies. Their license files are copied here from
the installed distributions; INVENTORY.txt records the build environment.
Individual projects retain their copyrights and license terms.

This release uses unmodified Qt 6.11.2 and PySide6/Shiboken6 6.11.2 under the
applicable LGPL-3.0 terms, with the license texts and upstream copyright notices
under `upstream/`. Only Qt Base, Declarative (QML/Quick/Basic Controls), and SVG
runtime modules are included. Optional PDF, Quick 3D, browser, chart, virtual
keyboard, and QML debugger/profiler plugins are excluded. A build fails if an
unreviewed Qt runtime module appears. Individual bundled third-party components
retain their own licenses; this notice does not replace those texts.

The matching source archives are provided alongside the binaries in
**Job-Tracker-AI-Dependency-Sources.zip** on the same GitHub release:
https://github.com/khalifehbasiri/Job-Tracker-AI/releases/tag/v0.2.0

The archive contains Qt Base, Qt Declarative, Qt SVG, PySide/Shiboken sources,
and certifi's matching MPL-2.0 source. SOURCE-MANIFEST.json records each exact
upstream URL and SHA-256. Source downloads are checksum-verified before a binary
build. The application source is available from that release tag as well.

## Library replacement and installation information

Qt and PySide6 DLLs remain separate files in `_internal/PySide6` and
`_internal/shiboken6` rather than being statically linked into the executable.
You may study, modify, replace, and relink these libraries, including reverse
engineering needed to debug your modifications. This application imposes no
contractual restriction on those rights and does not check vendor signatures on
replacement libraries. Do not remove upstream copyright notices or license texts.

To run modified libraries:

1. Quit the app and copy the complete portable folder to a writable directory.
2. Extract the corresponding source archives and build the modified Qt modules
   and/or PySide/Shiboken using the upstream build instructions linked below.
   Use Windows x64 and compatible Qt 6.11.2/PySide6 6.11.2 ABIs; preserve the
   Python 3.13 ABI and Microsoft runtime compatibility for Python bindings.
3. Back up the original DLL/plugin files. Replace the matching files under
   `_internal/PySide6` or `_internal/shiboken6`, keeping their relative paths and
   filenames. Replace dependent plugins/bindings too if your changes alter their ABI.
4. Run `Job-Tracker-AI.exe` from the copied folder. Rebuild the whole application
   from the tagged source and `packaging/windows.spec` when binding interfaces
   change. There is no application activation key or device lockdown to bypass.

Build tools must be installed separately; ordinary users do not need them to run
the app. The source archives retain upstream build files and additional notices.

Matching Qt/PySide6 sources and build instructions are available from:

- https://download.qt.io/official_releases/qt/
- https://code.qt.io/cgit/pyside/pyside-setup.git/
- https://doc.qt.io/qtforpython-6/gettingstarted/index.html
- https://doc.qt.io/qt-6/build-sources.html
- https://www.qt.io/licensing/open-source-lgpl-obligations

The application's own source is MIT licensed and available at
https://github.com/khalifehbasiri/Job-Tracker-AI.
