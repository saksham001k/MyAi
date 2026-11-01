param([string]$MemoryData = 'D:\AI\earthma-memory', [string]$EarthmaRoot = '')
$ErrorActionPreference = 'Stop'
$appRoot = Split-Path -Parent $PSScriptRoot
if (-not $EarthmaRoot) { $EarthmaRoot = Join-Path (Split-Path -Parent $appRoot) 'Earthma' }
if ((Test-Path -LiteralPath (Join-Path $EarthmaRoot 'earthma\memory_service.py')) -and (Test-Path -LiteralPath $MemoryData)) {
    $dataFolder = Join-Path $appRoot 'data'
    New-Item -ItemType Directory -Path $dataFolder -Force | Out-Null
    $configFile = Join-Path $dataFolder 'desktop-memory.json'
    if (-not (Test-Path -LiteralPath $configFile)) {
        $config = @{earthma=$EarthmaRoot; data=$MemoryData; port=8877} | ConvertTo-Json
        [System.IO.File]::WriteAllText($configFile, $config)
    }
}
$python = Join-Path $appRoot '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run scripts/setup_local.py first to create the MyAi environment.' }
$shell = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$programs = [Environment]::GetFolderPath('Programs')
foreach ($folder in @($desktop, $programs)) {
    $shortcut = $shell.CreateShortcut((Join-Path $folder 'KISS.lnk'))
    $shortcut.TargetPath = $python
    $shortcut.Arguments = '"' + (Join-Path $appRoot 'desktop.py') + '"'
    $shortcut.WorkingDirectory = $appRoot
    $shortcut.Description = 'KISS — your local assistant'
    $icon = Join-Path $appRoot 'web\kiss.ico'
    if (Test-Path -LiteralPath $icon) { $shortcut.IconLocation = $icon }
    $shortcut.Save()
    $oldLink = Join-Path $folder 'MyAi.lnk'
    if (Test-Path -LiteralPath $oldLink) {
        $old = $shell.CreateShortcut($oldLink)
        if ($old.Arguments -eq $shortcut.Arguments -and $old.TargetPath -eq $shortcut.TargetPath) {
            Remove-Item -LiteralPath $oldLink
        }
    }
}
Write-Output 'KISS shortcuts installed on the desktop and in the Start menu.'
