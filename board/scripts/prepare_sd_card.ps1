param(
    [Parameter(Mandatory=$true)][string]$DriveLetter,
    [string]$ImagesDir = '',
    [switch]$ReplaceExisting
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Board = Join-Path $Root 'board'
$Data = Join-Path $Root 'data'
if (-not $ImagesDir) { $ImagesDir = Join-Path $Data 'images_philips_a3c' }

$Letter = $DriveLetter.Trim().TrimEnd(':').ToUpperInvariant()
if ($Letter -notmatch '^[A-Z]$') { throw 'Drive letter must be one letter, e.g. F.' }
$Sd = "$Letter`:\"
if (-not (Test-Path -LiteralPath $Sd)) { throw "drive not found: $Sd" }
$D = New-Object System.IO.DriveInfo($Sd)
if (-not $D.IsReady) { throw "drive not ready: $Sd" }
if ($D.DriveFormat -ne 'FAT32') { throw "need FAT32, current: $($D.DriveFormat)" }

$BootZip = Join-Path $Board 'sd_boot_image.zip'
$Wzip = Join-Path $Board 'weights\sd_weights_oct20.zip'
$WTarget = Join-Path $Sd 'yolov4_tiny_weights'
$YTarget = Join-Path $Sd 'yolo_test'
foreach ($p in @($BootZip, $Wzip)) { if (-not (Test-Path -LiteralPath $p)) { throw "missing: $p" } }
if (-not (Test-Path -LiteralPath $ImagesDir)) { throw "images dir not found: $ImagesDir" }

$Conflicts = @($WTarget, $YTarget, (Join-Path $Sd 'BOOT.bin')) | Where-Object { Test-Path -LiteralPath $_ }
if ($Conflicts.Count -gt 0) {
    if (-not $ReplaceExisting) { throw "SD already has project files; use -ReplaceExisting" }
    $Ans = Read-Host 'Replace existing files on SD card? type YES'
    if ($Ans -cne 'YES') { Write-Host 'cancelled'; exit 1 }
    foreach ($p in $Conflicts) { Remove-Item -LiteralPath $p -Recurse -Force }
}

$Python = $null
foreach ($Name in @('py.exe', 'python.exe')) {
    $Cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $Cmd -or $Cmd.Source -like '*\WindowsApps\*') { continue }
    $Probe = & $Cmd.Source -c "import sys;print(sys.version_info[0])" 2>$null
    if ($LASTEXITCODE -eq 0 -and "$Probe".Trim() -eq '3') { $Python = $Cmd.Source; break }
}
$Stage = Join-Path $env:TEMP ('speckle_card_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Force -Path $Stage | Out-Null
if ($Python) {
    $Enc = Join-Path $PSScriptRoot 'encode_images.py'
    & $Python $Enc $ImagesDir $Stage 200
    if ($LASTEXITCODE -ne 0) { throw 'encode failed' }
} else {
    # fallback: copy pre-encoded files if present
    $n = 0
    Get-ChildItem -LiteralPath $ImagesDir -File | Where-Object { $_.Name -match '^img\d+\.(bin|png)$' } |
        ForEach-Object { Copy-Item $_.FullName $Stage -Force; $n++ }
    if ($n -eq 0) { throw 'Python 3 not found and no pre-encoded img*.bin in images dir' }
    $bins = @(Get-ChildItem -LiteralPath $Stage -Filter 'img*.bin').Count
    Set-Content -LiteralPath (Join-Path $Stage 'img_num.txt') -Value $bins -Encoding ASCII
}

# weights (zip root already is yolov4_tiny_weights/)
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::ExtractToDirectory($Wzip, $Sd, [System.Text.Encoding]::UTF8)
[System.IO.Compression.ZipFile]::ExtractToDirectory($BootZip, $Sd, [System.Text.Encoding]::UTF8)

New-Item -ItemType Directory -Force -Path $YTarget | Out-Null
Copy-Item -Path (Join-Path $Stage '*') -Destination $YTarget -Force -Recurse
Remove-Item $Stage -Recurse -Force -ErrorAction SilentlyContinue

$bins = @(Get-ChildItem -LiteralPath $YTarget -Filter 'img*.bin').Count
$pngs = @(Get-ChildItem -LiteralPath $YTarget -Filter 'img*.png').Count
$num = (Get-Content -LiteralPath (Join-Path $YTarget 'img_num.txt') -ErrorAction SilentlyContinue).Trim()
if ($bins -eq 0 -or $bins -ne $pngs -or $num -ne "$bins") {
    throw "card test set incomplete: bins=$bins pngs=$pngs img_num=$num"
}
Write-Host "SD card ready: $Sd" -ForegroundColor Green
Write-Host "  BOOT.bin             <- board/sd_boot_image.zip"
Write-Host "  yolov4_tiny_weights  <- board/weights/sd_weights_oct20.zip (42 files)"
Write-Host "  yolo_test            <- $ImagesDir ($bins frames)"
