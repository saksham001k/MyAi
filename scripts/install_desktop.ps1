$ErrorActionPreference = 'Stop'
$appRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $appRoot '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run scripts/setup_local.py first to create the MyAi environment.' }
$shell = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$programs = [Environment]::GetFolderPath('Programs')
foreach ($folder in @($desktop, $programs)) {
    $shortcut = $shell.CreateShortcut((Join-Path $folder 'MyAi.lnk'))
    $shortcut.TargetPath = $python
    $shortcut.Arguments = '"' + (Join-Path $appRoot 'desktop.py') + '"'
    $shortcut.WorkingDirectory = $appRoot
    $shortcut.Description = 'Open your local MyAi assistant'
    $icon = Join-Path $appRoot 'web\myai.ico'
    if (Test-Path -LiteralPath $icon) { $shortcut.IconLocation = $icon }
    $shortcut.Save()
}
Write-Output 'MyAi shortcuts installed on the desktop and in the Start menu.'
