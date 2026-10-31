param([string]$SourceDir='', [Parameter(Mandatory=$true)][string]$DriveLetter)
$ErrorActionPreference = 'Stop'
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not $SourceDir) {
    Add-Type -AssemblyName System.Windows.Forms
    $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
    $dlg.Description = 'Select image folder (png/jpg/bmp)'
    $dlg.ShowNewFolderButton = $false
    if ($dlg.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { exit 1 }
    $SourceDir = $dlg.SelectedPath
}
if (-not (Test-Path -LiteralPath $SourceDir)) { throw "source not found: $SourceDir" }
$Letter = $DriveLetter.Trim().TrimEnd(':').ToUpperInvariant()
$Sd = "$Letter`:\"
if (-not (Test-Path -LiteralPath $Sd)) { throw "drive not found: $Sd" }
$YTarget = Join-Path $Sd 'yolo_test'

$Python = $null
foreach ($Name in @('py.exe', 'python.exe')) {
    $Cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $Cmd -or $Cmd.Source -like '*\WindowsApps\*') { continue }
    $Probe = & $Cmd.Source -c "import sys;print(sys.version_info[0])" 2>$null
    if ($LASTEXITCODE -eq 0 -and "$Probe".Trim() -eq '3') { $Python = $Cmd.Source; break }
}
if (-not $Python) { throw 'Python 3 not found (needed to encode images)' }
$Deps = & $Python -c "import importlib.util as u;print(','.join(m for m in ('numpy','PIL') if u.find_spec(m) is None))" 2>$null
if ($Deps) { throw "missing deps: $Deps ; run pip install numpy pillow" }

if (Test-Path -LiteralPath $YTarget) {
    $Ans = Read-Host 'Replace yolo_test on SD card? type YES'
    if ($Ans -cne 'YES') { Write-Host 'cancelled'; exit 1 }
    Remove-Item -LiteralPath $YTarget -Recurse -Force
}
$Enc = Join-Path $PSScriptRoot 'encode_images.py'
& $Python $Enc $SourceDir $YTarget 200
if ($LASTEXITCODE -ne 0) { throw 'encode failed' }
$bins = @(Get-ChildItem -LiteralPath $YTarget -Filter 'img*.bin').Count
Write-Host "written $bins frames to $YTarget" -ForegroundColor Green
