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

$LastImageDirFile = Join-Path $PSScriptRoot 'last_image_dir.txt'
function Get-ImageCount([string]$Dir) {
    if (-not (Test-Path -LiteralPath $Dir)) { return 0 }
    $n = 0
    foreach ($pat in @('*.png', '*.jpg', '*.jpeg', '*.bmp')) {
        $n += @(Get-ChildItem -LiteralPath $Dir -Filter $pat -File -ErrorAction SilentlyContinue).Count
    }
    return $n
}

$ChosenBy = ''
if (-not $ImageDir) {
    # 1) 上次准备图片时记住的目录
    if (Test-Path -LiteralPath $LastImageDirFile) {
        $Cand = (Get-Content -LiteralPath $LastImageDirFile -Raw -ErrorAction SilentlyContinue).Trim()
        if ($Cand -and (Test-Path -LiteralPath $Cand) -and (Get-ImageCount $Cand) -ge $Need) {
            $ImageDir = $Cand; $ChosenBy = 'remembered'
        }
    }
    # 2) data/images_* 自动匹配
    if (-not $ImageDir) {
        $DataDir = Join-Path $Root 'data'
        $Cands = @(Get-ChildItem -LiteralPath $DataDir -Directory -Filter 'images_*' -ErrorAction SilentlyContinue |
            Where-Object { (Get-ImageCount $_.FullName) -ge $Need } |
            Sort-Object { Get-ImageCount $_.FullName })
        if ($Cands.Count -ge 1) {
            $ImageDir = $Cands[0].FullName; $ChosenBy = 'auto'
            if ($Cands.Count -gt 1) { Write-Host "[WARN] multiple candidates cover frames 0..$($Frames[-1]); choose -ImageDir if wrong" -ForegroundColor Yellow }
        }
    }
    # 3) 询问用户（文件夹选择框）
    if (-not $ImageDir) {
        Add-Type -AssemblyName System.Windows.Forms
        $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
        $dlg.Description = "选择测试图片文件夹（需覆盖帧 0..$($Frames[-1])，支持 0001.png / img0.png 等命名）"
        $dlg.ShowNewFolderButton = $false
        if ($dlg.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
            throw "未选择图片目录。请用 -ImageDir 指定测试图片文件夹（需覆盖帧 0..$($Frames[-1])）。"
        }
        $ImageDir = $dlg.SelectedPath; $ChosenBy = 'manual'
    }
}
if (-not (Test-Path -LiteralPath $ImageDir)) { throw "image dir not found: $ImageDir" }
$ImgCount = Get-ImageCount $ImageDir
if ($ImgCount -lt $Need) { Write-Host "[WARN] only $ImgCount images, need $Need; some frames may be skipped" -ForegroundColor Yellow }
Set-Content -LiteralPath $LastImageDirFile -Value $ImageDir -Encoding UTF8

$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$Output = Join-Path $Board ("results\render_$Stamp")
Write-Host "log   : $SerialLog ($($Frames.Count) frames)"
Write-Host "images: $ImageDir"
& $Python $Renderer $SerialLog $ImageDir $Output
if ($LASTEXITCODE -ne 0) { throw "render failed, exit code $LASTEXITCODE" }
Write-Host "results: $Output" -ForegroundColor Green
Start-Process explorer.exe $Output
