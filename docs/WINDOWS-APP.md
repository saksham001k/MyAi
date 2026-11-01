# KISS for Windows

Double-click **KISS** on your desktop or in the Start menu. The local service starts
automatically and the interface opens in its own window. Opening it again brings
the existing window forward. Closing the window shuts down its service and model.
Existing models, settings, conversations and projects remain in the same folder.

You can also double-click `MyAi.vbs` or `Start-MyAi.bat` in the project folder;
these older filenames continue to launch KISS.
No terminal needs to stay open. Model selection and downloads remain in Settings.

To recreate shortcuts after moving the project, run `scripts/install_desktop.ps1`.
The installer replaces this installation's old MyAi shortcuts with KISS shortcuts
and its cyan K logo. The native window and taskbar also use the KISS name and mark.
This is a launcher for the existing installation, not a standalone installer:
keep the project folder and its `.venv` in place.

The desktop window uses pywebview and Microsoft Edge WebView2. On first launch,
if the window component is missing, a setup window installs
`requirements-desktop.txt`; this needs internet. A missing Python environment
requires the existing one-time `scripts/setup_local.py` setup.
For launch errors, see `data/desktop.log`. Logs stay local and are Git-ignored.

## Shared memory without terminals

On a configured PC, the desktop app starts Earthma shared memory automatically
and connects before loading the interface. An existing authenticated service is
reused and left running when MyAi closes. A service started by MyAi closes with
the app; saved memory remains on disk and is available on the next launch.

The local, Git-ignored `data/desktop-memory.json` contains `earthma` (Earthma
checkout folder), `data` (existing memory-data folder), and `port` (usually 8877).
The shortcut installer creates this configuration if sibling Earthma and
`D:\AI\earthma-memory` exist. Use `-MemoryData` and `-EarthmaRoot` installer
arguments for other locations. An existing configuration is preserved.
No access credentials are included in Git.

## Finding your way back

Settings has a sticky **Back to conversation** button. Both **Add models** and
**Models & performance** have **Back to settings** buttons. Escape collapses an
open model section first, then closes settings. Memory and file dialogs have
sticky Close controls and support Escape; closing them restores keyboard focus.
Close remains available while memory requests load. Saved work and creations
offer **Back to chat** once the current operation has stopped or finished.

Developer terminal entrypoints (`run.py` and `scripts/local.py start`) remain
available. Avoid starting a terminal instance alongside the desktop application.
