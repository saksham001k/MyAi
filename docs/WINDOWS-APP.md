# MyAi for Windows

Double-click **MyAi** on your desktop or in the Start menu. The local service starts
automatically and the interface opens in its own window. Opening it again brings
the existing window forward. Closing the window shuts down its service and model.
Existing models, settings, conversations and projects remain in the same folder.

You can also double-click `MyAi.vbs` or `Start-MyAi.bat` in the project folder.
No terminal needs to stay open. Model selection and downloads remain in Settings.

To recreate shortcuts after moving the project, run `scripts/install_desktop.ps1`.
This is a launcher for the existing installation, not a standalone installer:
keep the project folder and its `.venv` in place.

The desktop window uses pywebview and Microsoft Edge WebView2. On first launch,
if the window component is missing, a setup window installs
`requirements-desktop.txt`; this needs internet. A missing Python environment
requires the existing one-time `scripts/setup_local.py` setup.
For launch errors, see `data/desktop.log`. Logs stay local and are Git-ignored.

Developer terminal entrypoints (`run.py` and `scripts/local.py start`) remain
available. Avoid starting a terminal instance alongside the desktop application.
