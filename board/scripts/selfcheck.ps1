param([string]$SdRoot='')
$ErrorActionPreference = 'Continue'
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$fail = 0; $warn = 0
function Ok($m) { Write-Host "[PASS] $m" -ForegroundColor Green }
function Wn($m) { Write-Host "[WARN] $m" -ForegroundColor Yellow; $script:warn++ }
function Er($m) { Write-Host "[FAIL] $m" -ForegroundColor Red; $script:fail++ }

Write-Host '=========================================='
Write-Host '  Package self-check (run this first)'
Write-Host '=========================================='

$ver = Join-Path $Root 'README.md'
if (Test-Path -LiteralPath $ver) { Ok "README.md present" } else { Er 'README.md missing' }

$req = @(
    'src\software\debug.cpp', 'src\software\main.cpp',
    'src\hls\conv.cpp', 'src\hls\std_conv.cpp',
    'board\bitstream\system_wrapper.bit', 'board\bitstream\yolov4_tiny.elf',
    'board\bitstream\BOOKEEP'
)
$req = @(
    'src\software\debug.cpp', 'src\software\main.cpp',
    'src\hls\conv.cpp', 'src\hls\std_conv.cpp',
    'board\bitstream\system_wrapper.bit', 'board\bitstream\yolov4_tiny.elf',
    'board\sd_boot_image.zip', 'board\weights\sd_weights_oct20.zip',
    'data\images_toshiba_a4c\img0.png', 'data\labels_toshiba_a4c\g0.txt',
    'sim\scripts\paths.py', 'skill\README.md', 'report\design_report.md'
)
foreach ($r in $req) {
    $p = Join-Path $Root $r
    if (Test-Path -LiteralPath $p) { Ok "file: $r" } else { Er "missing: $r" }
}
$elf = Join-Path $Root 'board\bitstream\yolov4_tiny.elf'
if (Test-Path -LiteralPath $elf) {
    $t = [System.IO.File]::ReadAllBytes($elf)
    $s = [System.Text.Encoding]::ASCII.GetString($t)
    if ($s.Contains('ALL DONE') -and $s.Contains('image num = ')) { Ok 'ELF is the new firmware (K-line output)' }
    else { Wn 'ELF may be an old build (no ALL DONE/image num strings)' }
}
$dbg = Join-Path $Root 'src\software\debug.cpp'
if (Test-Path -LiteralPath $dbg) {
    $dt = Get-Content -LiteralPath $dbg -Raw -Encoding UTF8
    if ($dt -match 'cbest') { Ok 'debug.cpp uses YOLO class-assignment rule (latest)' }
    else { Wn 'debug.cpp looks like the old per-class-argmax rule' }
}
$sc = Join-Path $Root 'sim\results\summary_metrics.csv'
if (Test-Path -LiteralPath $sc) {
    $st = Get-Content -LiteralPath $sc -Raw -Encoding UTF8
    if ($st -match 'newrule') { Ok 'sim/results contains new-rule metrics' } else { Wn 'sim/results has no new-rule row' }
}

# PC env
$Python = $null
foreach ($Name in @('py.exe', 'python.exe')) {
    $Cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $Cmd -or $Cmd.Source -like '*\WindowsApps\*') { continue }
    $Probe = & $Cmd.Source -c "import sys;print(sys.version_info[0])" 2>$null
    if ($LASTEXITCODE -eq 0 -and "$Probe".Trim() -eq '3') { $Python = $Cmd.Source; break }
}
if ($Python) {
    Ok "Python: $Python"
    $d = & $Python -c "import importlib.util as u;print(','.join(m for m in ('numpy','PIL') if u.find_spec(m) is None))" 2>$null
    if ($d) { Wn "Python missing deps: $d (pip install numpy pillow)" } else { Ok 'numpy / pillow available' }
} else {
    Wn 'Python 3 not found (only needed for encode/render)'
}
$ports = @([System.IO.Ports.SerialPort]::GetPortNames() | Sort-Object)
if ($ports.Count -gt 0) { Ok ("COM ports: " + ($ports -join ', ')) } else { Wn 'no COM port (USB-UART not connected)' }
if (Test-Path 'C:\Xilinx\SDK') { Ok 'Xilinx SDK installed' } else { Write-Host '       no Xilinx SDK (JTAG path unavailable; SD boot still works)' }

# SD card
$vols = @(Get-Volume -ErrorAction SilentlyContinue | Where-Object { $_.DriveType -eq 'Removable' })
if (-not $SdRoot) {
    if ($vols.Count -eq 1) { $SdRoot = "$($vols[0].DriveLetter):" }
}
if (-not $SdRoot) {
    Wn 'no SD card reader detected (needed by prepare_sd_card)'
} else {
    $letter = $SdRoot.Trim().TrimEnd(':').ToUpperInvariant()
    $sd = "$letter`:\"
    $bootzip = Join-Path $Root 'board\sd_boot_image.zip'
    $cb = Join-Path $sd 'BOOT.bin'
    if (Test-Path -LiteralPath $cb) {
        $tmp = [System.IO.Path]::GetTempFileName()
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zip = [System.IO.Compression.ZipFile]::OpenRead($bootzip)
        $entry = $zip.Entries | Where-Object { $_.FullName -eq 'BOOT.bin' } | Select-Object -First 1
        if ($entry) {
            $s = $entry.Open(); $fs = [System.IO.File]::Create($tmp); $s.CopyTo($fs); $fs.Close(); $s.Close()
        }
        $zip.Dispose()
        if ((Get-FileHash -LiteralPath $cb -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $tmp -Algorithm SHA256).Hash) {
            Ok 'SD BOOT.bin matches this package'
        } else { Wn 'SD BOOT.bin differs from package (rewrite with prepare_sd_card.bat)' }
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
    } else { Wn 'SD card has no BOOT.bin (run prepare_sd_card.bat)' }
    $w = Join-Path $sd 'yolov4_tiny_weights'
    if (Test-Path -LiteralPath $w) {
        $cnt = @(Get-ChildItem -LiteralPath $w -Recurse -File).Count
        if ($cnt -eq 42) { Ok 'SD weights: 42 files' } else { Wn "SD weights file count=$cnt (expect 42)" }
    } else { Wn 'SD card has no yolov4_tiny_weights' }
    $y = Join-Path $sd 'yolo_test'
    if (Test-Path -LiteralPath $y) {
        $b = @(Get-ChildItem -LiteralPath $y -Filter 'img*.bin').Count
        $n = (Get-Content -LiteralPath (Join-Path $y 'img_num.txt') -ErrorAction SilentlyContinue).Trim()
        if ($b -gt 0 -and "$n" -eq "$b") { Ok "SD test set: $b frames (img_num=$n)" } else { Wn "SD test set abnormal: bins=$b img_num=$n" }
    } else { Wn 'SD card has no yolo_test' }
}

Write-Host ''
if ($fail -eq 0 -and $warn -eq 0) { Write-Host 'SELF-CHECK PASSED' -ForegroundColor Green; exit 0 }
elseif ($fail -eq 0) { Write-Host "SELF-CHECK: $warn warning(s)" -ForegroundColor Yellow; exit 0 }
else { Write-Host "SELF-CHECK: $fail error(s), $warn warning(s)" -ForegroundColor Red; exit 1 }
