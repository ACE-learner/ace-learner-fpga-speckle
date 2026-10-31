param([string]$SerialLog='', [string]$ImageDir='')
$ErrorActionPreference = 'Stop'
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Board = Join-Path $Root 'board'
$LogDir = Join-Path $Board 'logs'
if (-not (Test-Path -LiteralPath $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }

$PythonCandidates = @()
foreach ($Name in @('py.exe', 'python.exe', 'python3.exe')) {
    $Cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($Cmd -and $Cmd.Source -notlike '*\WindowsApps\*') { $PythonCandidates += $Cmd.Source }
}
$Python = $null
foreach ($Candidate in $PythonCandidates) {
    if (-not $Candidate) { continue }
    $Probe = & $Candidate -c "import sys;print(sys.version_info[0])" 2>$null
    if ($LASTEXITCODE -eq 0 -and "$Probe".Trim() -eq '3') { $Python = $Candidate; break }
}
if (-not $Python) { throw 'Python 3 not found. Install Python 3.8+ and add to PATH.' }
$Deps = & $Python -c "import importlib.util as u;print(','.join(m for m in ('numpy','PIL') if u.find_spec(m) is None))" 2>$null
if ($Deps) { throw ("Missing Python deps: $Deps ; run: `"$Python`" -m pip install numpy pillow") }

$Renderer = Join-Path $PSScriptRoot 'render_from_serial.py'
if (-not (Test-Path -LiteralPath $Renderer)) { throw "missing render_from_serial.py" }

if (-not $SerialLog) {
    $Logs = @(Get-ChildItem -LiteralPath $LogDir -Filter '*.txt' -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending)
    foreach ($f in $Logs) {
        $t = Get-Content -LiteralPath $f.FullName -Raw -ErrorAction SilentlyContinue
        if ([string]::IsNullOrEmpty($t)) { continue }
        if (-not [regex]::IsMatch($t, '(?m)^K \d+ ')) { continue }
        $SerialLog = $f.FullName; break
    }
}
if (-not $SerialLog -or -not (Test-Path -LiteralPath $SerialLog)) {
    throw "No serial log with K lines found under board/logs. Run read_serial.bat first."
}

$Text = Get-Content -LiteralPath $SerialLog -Raw -ErrorAction SilentlyContinue
$Frames = @([regex]::Matches($Text, '(?m)^K (\d+) \d+ ') |
    ForEach-Object { [int]$_.Groups[1].Value } | Sort-Object -Unique)
if ($Frames.Count -eq 0) { throw "No K lines in log: $SerialLog" }
$Need = $Frames[-1] + 1

if (-not $ImageDir) {
    $DataDir = Join-Path $Root 'data'
    $Cands = @(Get-ChildItem -LiteralPath $DataDir -Directory -Filter 'images_*' -ErrorAction SilentlyContinue |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'img0.png') } |
        Where-Object { @(Get-ChildItem -LiteralPath $_.FullName -Filter 'img*.png' -File).Count -ge $Need } |
        Sort-Object { @(Get-ChildItem -LiteralPath $_.FullName -Filter 'img*.png' -File).Count })
    if ($Cands.Count -ge 1) {
        $ImageDir = $Cands[0].FullName
        Write-Host "auto-selected images: $ImageDir" -ForegroundColor Green
        if ($Cands.Count -gt 1) { Write-Host "[WARN] multiple candidates cover frames 0..$($Frames[-1]); choose -ImageDir if wrong" -ForegroundColor Yellow }
    } else {
        throw "No image folder under data/ covers frame 0..$($Frames[-1]); pass -ImageDir"
    }
}
if (-not (Test-Path -LiteralPath (Join-Path $ImageDir 'img0.png'))) { throw "no img0.png in $ImageDir" }
$ImgCount = @(Get-ChildItem -LiteralPath $ImageDir -Filter 'img*.png' -File).Count
if ($ImgCount -lt $Need) { Write-Host "[WARN] only $ImgCount images, need $Need" -ForegroundColor Yellow }

$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$Output = Join-Path $Board ("results\render_$Stamp")
Write-Host "log   : $SerialLog ($($Frames.Count) frames)"
Write-Host "images: $ImageDir"
& $Python $Renderer $SerialLog $ImageDir $Output
if ($LASTEXITCODE -ne 0) { throw "render failed, exit code $LASTEXITCODE" }
Write-Host "results: $Output" -ForegroundColor Green
Start-Process explorer.exe $Output
