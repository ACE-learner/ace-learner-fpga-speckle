param([string]$SdkPath='', [switch]$DryRun)
$ErrorActionPreference = 'Stop'
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Tcl = Join-Path $PSScriptRoot 'run_on_board.tcl'
$Bs = Join-Path $Root 'board\bitstream'

Write-Host '=========================================='
Write-Host '  JTAG download and run (bitstream + ELF)'
Write-Host '  Require: JTAG cable + board powered + SDK 2018.3'
Write-Host '=========================================='

foreach ($f in @('system_wrapper.bit', 'yolov4_tiny.elf', 'ps7_init.tcl')) {
    if (-not (Test-Path -LiteralPath (Join-Path $Bs $f))) { throw "missing board/bitstream/$f" }
}

$Candidates = @()
if ($SdkPath) { $Candidates += (Join-Path $SdkPath 'bin\xsct.bat'); $Candidates += (Join-Path $SdkPath 'xsct.bat') }
foreach ($EnvName in @('XILINX_XSCT', 'XILINX_SDK')) {
    $v = [Environment]::GetEnvironmentVariable($EnvName)
    if ($v) { $Candidates += $v; $Candidates += (Join-Path $v 'bin\xsct.bat') }
}
$Candidates += 'C:\Xilinx\SDK\2018.3\bin\xsct.bat'
Get-ChildItem 'C:\Xilinx\SDK' -Directory -ErrorAction SilentlyContinue |
    Sort-Object Name -Descending | ForEach-Object { $Candidates += (Join-Path $_.FullName 'bin\xsct.bat') }
$Cmd = Get-Command xsct.bat -ErrorAction SilentlyContinue
if ($Cmd) { $Candidates += $Cmd.Source }
$Xsct = $Candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1

if (-not $Xsct) {
    Write-Host '[ERROR] xsct.bat not found (Vivado/SDK 2018.3).' -ForegroundColor Red
    Write-Host '        Install SDK 2018.3, or: run_jtag.bat -SdkPath "C:\Xilinx\SDK\2018.3"' -ForegroundColor Yellow
    Write-Host '        Without SDK: use SD-card boot instead (prepare_sd_card.bat + BOOT switch to SD).' -ForegroundColor Yellow
    exit 2
}
Write-Host "xsct : $Xsct"
Write-Host "tcl  : $Tcl"
if ($DryRun) {
    Write-Host ''
    Write-Host '[DryRun] command:' -ForegroundColor Green
    Write-Host ('  "{0}" "{1}"' -f $Xsct, $Tcl)
    exit 0
}
Write-Host ''
Write-Host 'Tip: run read_serial.bat FIRST, then this script, to capture frame 0.' -ForegroundColor Yellow
Write-Host ("Current COM ports: " + (([System.IO.Ports.SerialPort]::GetPortNames()) -join ', '))
$Ans = Read-Host 'Serial capture already started? (Enter=continue, n=cancel)'
if ($Ans -and $Ans.Trim().ToLower() -eq 'n') { Write-Host 'cancelled'; exit 1 }

& $Xsct $Tcl
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] xsct exit code $LASTEXITCODE" -ForegroundColor Red
    Write-Host 'Check: JTAG cable/driver (0403:6014), board power, hw_server not occupied.' -ForegroundColor Yellow
    exit $LASTEXITCODE
}
Write-Host 'Download done. Watch UART for: Yolo4 Tiny Test / image num / K lines / ALL DONE' -ForegroundColor Green
exit 0
