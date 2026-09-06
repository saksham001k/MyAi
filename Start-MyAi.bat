@echo off
cd /d "%~dp0"
if exist MyAi.exe (
  MyAi.exe
) else (
  python run.py
)
if errorlevel 1 pause
