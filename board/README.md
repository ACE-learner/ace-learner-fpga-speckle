# 板端（Board）运行产物与脚本

## 1. 硬件连接

| 接口 | 连接 | 说明 |
|---|---|---|
| USB_JTAG（左侧） | 电脑 USB | FTDI，`0403:6014`，用于下载位流/程序 |
| USB_UART | 电脑 USB | CH340，`1A86:7523`，115200-8-N-1 |
| SD 卡槽 | SD 卡（FAT32） | 存放权重与测试图 |
| DC 电源 | 12 V | — |

## 2. 产物

| 文件 | 用途 |
|---|---|
| `bitstream/system_wrapper.bit` | PL 位流（与 `build/reports/` 同一次实现，SHA256 见 `build/implementation_report.md`） |
| `bitstream/yolov4_tiny.elf` | PS 应用（新规则：每框 argmax 类别 + 串口归一化关键点） |
| `bitstream/zynq_fsbl.elf` | FSBL |
| `bitstream/ps7_init.tcl` | PS 初始化 |
| `sd_boot_image.zip` | 解压得到 `BOOT.bin`（新固件；Zynq 启动镜像，文件名大写为运行时约束） |
| `boot.bif` | bootgen 打包模板（包内相对路径） |
| `weights/sd_weights_oct20.zip` | 解压得到 `yolov4_tiny_weights/`（42 个 BN 折叠 float32 权重，板端加载时 ×512 转 int16） |

## 3. 运行脚本（`scripts/`，全部包内相对路径）

| 脚本 | 作用 |
|---|---|
| `selfcheck.bat` | **先跑**：检查包完整性、固件版本、Python 依赖、SD 卡内容 |
| `prepare_sd_card.bat` | 一键写卡：从 `sd_boot_image.zip` 解出 BOOT.bin + 解压权重 + 编码测试集 |
| `prepare_images.bat` | 只替换卡上 `yolo_test/`（选自己的图片文件夹 → 编码 → 写卡） |
| `read_serial.bat` | 抓串口：**先运行**，会等串口出现；打开后再上电/复位，从第 0 帧开始抓 |
| `run_on_board.bat` | JTAG 下载位流 + ELF 并运行（自动找 xsct；`-DryRun` 只显示命令） |
| `render_results.bat` | 用最新串口日志出图，自动按帧号选择 `data/images_*` 图片目录，输出到 `board/results/` |
| `decode_sd_outputs.bat` | （旧固件 out 文件模式）解码 `out0_*.bin/out1_*.bin` 出图 |
| `eval_serial_vs_gt.bat` | 串口日志 vs GT 标注的命中率评测 |

命令行等价用法：

```bash
# 写卡（FAT32）
powershell -ExecutionPolicy Bypass -File scripts/prepare_sd_card.ps1 -DriveLetter F -ReplaceExisting

# 抓串口（先开）+ JTAG 运行
powershell -ExecutionPolicy Bypass -File scripts/read_serial.ps1 -Seconds 180
powershell -ExecutionPolicy Bypass -File scripts/run_jtag.ps1

# 出图 / 评测
powershell -ExecutionPolicy Bypass -File scripts/render_results.ps1
python scripts/eval_serial_vs_gt.py board/logs/log_toshiba_a4c_54f_newrule.txt data/images_toshiba_a4c data/labels_toshiba_a4c
```

## 4. 板端输出协议

启动：
```
Yolo4 Tiny Test
SD_Init = 0
image num = <N>
reading yolov4_tiny_weights\...
```

每帧：
```
image <i> time elapsed is <us> us
KPT <i> <arm_postprocess_us>
KP <i> 36/36
K <i> <cls> <nx> <ny> <nw> <nh> <score>     # 归一化坐标（0~1）
```

结束：
```
ALL DONE <N> frames
```

## 5. 实测日志（`logs/`）

| 文件 | 内容 |
|---|---|
| `log_toshiba_a4c_54f_newrule.txt` | **新规则**：TOSHIBA A4C 54 帧完整运行（帧 0..53，无截断），GT 命中 79.12% |
| `log_philips_a3c_50f.txt` | Philips A3C/rca 50 帧（旧规则） |
| `log_toshiba_a4c_54f.txt` | TOSHIBA A4C 54 帧（旧规则） |
| `log_toshiba_a4c_54f_run2.txt` | 同一测试集第二次运行（确定性对比用） |
| `log_powercycle_round1/2.txt` | 两次断电重启后的运行（确定性测试） |
| `log_philips_a3c_run_before_fix.txt` | 修复 SD/FatFS 问题前的运行（历史对照） |

> 旧规则日志对应"每类独立 argmax"解码，GT 命中 73.87%；新规则（每框 argmax 类别）为 79.12%。

## 6. 结果图（`results/`）

| 文件 | 说明 |
|---|---|
| `render_a4c_54f_newrule/` | 新规则 54 帧出图（`result_img*.png` + `demo.gif`） |
| `result_newrule_a4c54_img0.png` | 新规则单帧样例 |
| `result_sample_img0.png` | 旧规则单帧样例 |
| `result_montage_6frames.png` | 6 帧拼图 |
| `result_demo_50frames.gif` | 50 帧动画 |

## 7. 标准运行流程

```
① 双击 scripts\selfcheck.bat 自检
② 双击 scripts\prepare_sd_card.bat 写卡（输入盘符，YES 确认替换）
③ 卡插回板子，BOOT 拨到 SD 模式，上电
④ 双击 scripts\read_serial.bat（先开，等串口）→ 再按 PS_RST/上电
⑤ 串口出现 ALL DONE 后，双击 scripts\render_results.bat 出图
```

## 8. 功耗测量（板级，12V 输入）

板级功耗需实测（Vivado 的 3.212 W 是**片上估算**，不含 DDR/USB PHY/以太网 PHY/LDO）。

1. 接线：12V 电源/适配器 → 串联式 DC 功率计（或可调电源+电流表）→ 板子 DC 座（5.5×2.1，内正外负）
2. 测空闲：拔掉 SD 卡（或无 BOOT.bin），上电，稳定 10 s 记录 V/I/P
3. 测推理：插卡上电，串口看到 `image num`/`K` 行期间取 10~20 s 平均（54 帧约 23 s）
4. 记录表：

| 状态 | 电压 V | 电流 A | 功率 W | 备注 |
|---|---|---|---|---|
| 空闲 | 12.0 |  |  | 拔卡上电 |
| 推理中 | 12.0 |  |  | 54 帧运行窗口 |
| 推理结束 | 12.0 |  |  | ALL DONE 后 |

> 预计板级 4~7 W；报告时请把"板级实测"和"Vivado 片上估算 3.212 W"分开写。
