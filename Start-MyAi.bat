@echo off
cd /d "%~dp0"
if exist MyAi.exe (
  MyAi.exe
) else (
  start "" wscript.exe "%~dp0MyAi.vbs"
)
if errorlevel 1 pause
