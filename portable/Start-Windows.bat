@echo off
setlocal
"%~dp0Apps\windows-x86_64\MyAi.exe" --root "%~dp0Workspace" %*
if errorlevel 1 pause
