@echo off
setlocal
cd /d "%~dp0"
echo [*] Initializing MyAi for Windows...

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
  set "PY_CMD=python"
) else (
  where py >nul 2>nul
  if %ERRORLEVEL% equ 0 (
    set "PY_CMD=py"
  ) else (
      where node >nul 2>nul
      if %ERRORLEVEL% equ 0 if exist "dist\cli.js" (
          node dist\cli.js %*
          exit /b %ERRORLEVEL%
      )
      echo [!] Python 3 or Node.js was not found.
      exit /b 1
  )
)

if exist "runtime\win-x64\llama-server.exe" echo Runtime binary found.
%PY_CMD% run.py %*
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
