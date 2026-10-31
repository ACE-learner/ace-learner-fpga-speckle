param(
    [int]$Seconds = 180,
    [string]$Port = '',
    [int]$IdleStopSec = 15,
    [int]$PortWaitSec = 120,
    [switch]$NoPause
)

# 保存串口收到的所有字节（含启动错误），便于诊断 SD 启动。
# 注意：板子没上电时 USB-UART 可能还没枚举，所以本脚本会先"等串口出现"再打开，
#      打开后提示用户复位/上电，保证从第 0 帧开始抓。
$ErrorActionPreference = 'Continue'
$BoardDir = Split-Path $PSScriptRoot -Parent
$LogDir = Join-Path $BoardDir 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$Log = Join-Path $LogDir "serial_$Stamp.txt"

function Wait-Key {
    if ($NoPause) { return }
    try { Write-Host ''; Write-Host '按任意键关闭...'; $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') } catch {}
}

# ---------------- 1) 等待串口出现（板子没上电时不中止） ----------------
$Serial = $null
if ($Port) { $Port = $Port.Trim().ToUpperInvariant() }
$PortDeadline = (Get-Date).AddSeconds($PortWaitSec)
$StartWait = Get-Date
$LastHeartbeat = Get-Date
$PromptedMulti = $false
while ((Get-Date) -lt $PortDeadline) {
    try { $Names = @([System.IO.Ports.SerialPort]::GetPortNames() | Sort-Object) } catch { $Names = @() }

    if (-not $Port) {
        if ($Names.Count -eq 1) {
            $Port = $Names[0]
            Write-Host "自动选择串口: $Port"
        } elseif ($Names.Count -gt 1 -and -not $PromptedMulti) {
            Write-Host "检测到串口: $($Names -join ', ')"
            $Answer = Read-Host '请输入连接开发板的端口（直接回车=继续等待）'
            if ($Answer) { $Port = $Answer.Trim().ToUpperInvariant() } else { $PromptedMulti = $true }
        }
    }

    if ($Port -and ($Names -contains $Port)) {
        try {
            $Serial = New-Object System.IO.Ports.SerialPort $Port, 115200, 'None', 8, 'One'
            $Serial.ReadTimeout = 200
            $Serial.Open()
            break
        } catch {
            $Serial = $null
        }
    }

    if (((Get-Date) - $LastHeartbeat).TotalSeconds -ge 5) {
        $LastHeartbeat = Get-Date
        $Waited = [int]((Get-Date) - $StartWait).TotalSeconds
        if ($Port) {
            Write-Host ("  ... 等待串口 {0} 可用（已等 {1}s）；板子可能还没上电/USB-UART 没枚举" -f $Port, $Waited) -ForegroundColor DarkGray
        } else {
            Write-Host ("  ... 等待串口出现（已等 {1}s）；请检查 USB-UART 是否已插好、板子是否上电" -f $Port, $Waited) -ForegroundColor DarkGray
        }
    }
    Start-Sleep -Milliseconds 300
}

if (-not $Serial) {
    $Hint = if ($Port) { "串口 $Port 在 $PortWaitSec 秒内没有出现或打不开。" } else { "在 $PortWaitSec 秒内没有发现任何串口。" }
    Write-Host ($Hint + ' 请检查：USB-UART 是 CH340（驱动装好）、板子已上电、TX/RX 接对。') -ForegroundColor Red
    Wait-Key
    exit 1
}

Write-Host "已打开串口: $Port（115200）" -ForegroundColor Green
Write-Host '现在请给板子上电/按 PS_RST 复位，或运行 上板运行.bat —— 会从第 0 帧开始抓。' -ForegroundColor Green

# ---------------- 2) 抓取 ----------------
$Buffer = New-Object System.Text.StringBuilder
$Deadline = (Get-Date).AddSeconds($Seconds)
$SawStartMarker = $false
$LastData = $null
$StartTime = Get-Date
$LastHeartbeat = Get-Date
$StopReason = 'timeout'
try {
    while ((Get-Date) -lt $Deadline) {
        $Data = $null
        try {
            $Data = $Serial.ReadExisting()
        } catch {
            # 板子断电/重新上电时 USB-UART 可能掉线：自动重新等待并打开，不中断抓取
            try { $Serial.Close() } catch {}
            $Serial = $null
            Write-Host ''
            Write-Host '  ... 串口掉线，等待它重新出现（板子可能正在重新上电）...' -ForegroundColor Yellow
            $ReopenDeadline = (Get-Date).AddSeconds(120)
            while ((Get-Date) -lt $ReopenDeadline) {
                try { $Names2 = @([System.IO.Ports.SerialPort]::GetPortNames() | Sort-Object) } catch { $Names2 = @() }
                if ($Port -and ($Names2 -contains $Port)) {
                    try {
                        $Serial = New-Object System.IO.Ports.SerialPort $Port, 115200, 'None', 8, 'One'
                        $Serial.ReadTimeout = 200
                        $Serial.Open()
                        Write-Host "  ... 串口 $Port 已恢复" -ForegroundColor Green
                        break
                    } catch { $Serial = $null }
                }
                Start-Sleep -Milliseconds 300
            }
            if (-not $Serial) { $StopReason = 'port lost'; break }
            $LastData = $null
            continue
        }
        if ($Data) {
            Write-Host -NoNewline $Data
            [void]$Buffer.Append($Data)
            $LastData = Get-Date
            if (-not $SawStartMarker -and $Data.Contains('Yolo4 Tiny Test')) {
                $SawStartMarker = $true
                Write-Host '检测到 YOLO 启动标记。'
            }
            if ($Data -match 'ALL DONE') { $StopReason = 'ALL DONE'; break }
        } else {
            if (((Get-Date) - $LastHeartbeat).TotalSeconds -ge 5) {
                $LastHeartbeat = Get-Date
                $Waited = [int]((Get-Date) - $StartTime).TotalSeconds
                Write-Host ("  ... 仍在监听 {0}，已等 {1}s（等待板子上电/复位/串口输出）" -f $Port, $Waited) -ForegroundColor DarkGray
            }
        }
        if ($LastData -and ((Get-Date) - $LastData).TotalSeconds -ge $IdleStopSec) {
            $StopReason = "idle $IdleStopSec s"
            break
        }
        Start-Sleep -Milliseconds 100
    }
} finally {
    try { $Serial.Close() } catch {}
}

# ---------------- 3) 保存与诊断 ----------------
[System.IO.File]::WriteAllText($Log, $Buffer.ToString(), (New-Object System.Text.UTF8Encoding($false)))
Write-Host "读取结束（$StopReason），已保存: $Log"
$Captured = $Buffer.ToString()
$Processed = @([regex]::Matches($Captured, '(?m)^processing image (\d+)\s*$') |
    ForEach-Object { [int]$_.Groups[1].Value } | Sort-Object -Unique)
$KFrames = @([regex]::Matches($Captured, '(?m)^K (\d+) \d+ ') |
    ForEach-Object { [int]$_.Groups[1].Value } | Sort-Object -Unique)
$OutputFrames = @([regex]::Matches($Captured, '(?m)^writing yolo_test\\out1_(\d+)\.bin\s*$') |
    ForEach-Object { [int]$_.Groups[1].Value } | Sort-Object -Unique)
$InputErrors = @([regex]::Matches($Captured, 'ERROR\s*:\s*f_open returned\s+\d+')).Count

# 检查首帧是否完整（截断的帧类别数会明显少于正常值 ~30）
$KCountByFrame = @{}
foreach ($Match in [regex]::Matches($Captured, '(?m)^K (\d+) ')) {
    $Key = $Match.Groups[1].Value
    $KCountByFrame[$Key] = 1 + [int]($KCountByFrame[$Key])
}
$FirstFrameTruncated = $false
if ($KCountByFrame.Count -gt 0) {
    $FirstKey = ($KCountByFrame.Keys | ForEach-Object { [int]$_ } | Sort-Object)[0]
    if ($KCountByFrame["$FirstKey"] -lt 20) { $FirstFrameTruncated = $true }
}

if ($Buffer.Length -eq 0) {
    Write-Host "未收到任何串口数据：已确认 $Port 能打开，但板子没有输出。" -ForegroundColor Yellow
    Write-Host '请检查：板子是否真的上电/复位、TX/RX 是否接对、BOOT 模式是否正确。' -ForegroundColor Yellow
} elseif ($KFrames.Count -gt 0 -and $FirstFrameTruncated) {
    Write-Host ("首帧被截断：帧 {0} 只有 {1} 个点（正常约 30+）。" -f $KFrames[0], $KCountByFrame["$($KFrames[0])"]) -ForegroundColor Yellow
    Write-Host '原因：串口在板子开始跑之后才打开。正确做法：先运行本脚本，看到"已打开串口"后再复位/上电板子。' -ForegroundColor Yellow
} elseif ($KFrames.Count -gt 0) {
    if ($KFrames[0] -ne 0) {
        Write-Host ("已捕获关键点：帧 {0}..{1}（{2} 帧），首帧不是 0。" -f $KFrames[0], $KFrames[-1], $KFrames.Count) -ForegroundColor Yellow
        Write-Host '原因：串口监听在板子开始跑之后才打开。下次先运行本脚本（看到"已打开串口"），再上电/复位板子。' -ForegroundColor Yellow
    } else {
        Write-Host ("已捕获关键点：帧 0..{0}（{1} 帧），首帧完整。" -f $KFrames[-1], $KFrames.Count) -ForegroundColor Green
    }
} elseif ($Processed.Count -gt 0) {
    Write-Host ("已捕获 FPGA 推理输出：帧 {0} 至 {1}，其中 f_open 错误 {2} 次。" -f $Processed[0], $Processed[-1], $InputErrors) -ForegroundColor Yellow
    if ($Processed[0] -ne 0) {
        Write-Host '首帧不是 0：监听较晚。下次先运行本脚本，再给板子上电/复位。' -ForegroundColor Yellow
    }
} elseif ($OutputFrames.Count -gt 0) {
    Write-Host ("已捕获旧固件 out 文件输出：帧 {0} 至 {1}。" -f $OutputFrames[0], $OutputFrames[-1]) -ForegroundColor Yellow
} elseif (-not $SawStartMarker) {
    Write-Host '已保存原始串口内容，但未识别到 FPGA 推理输出；请将日志文件发来分析。' -ForegroundColor Yellow
}
Wait-Key
