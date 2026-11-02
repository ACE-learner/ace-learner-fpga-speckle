# 综合与实现报告（Synthesis & Implementation Report）

## 1. 目标器件与工具

| 项 | 值 |
|---|---|
| FPGA / SoC | Xilinx Zynq-7020（XC7Z020） |
| 工具链 | Vivado + Vitis/SDK **2018.3** |
| HLS 目标时钟 | 10 ns（100 MHz） |
| PL 实际时钟 FCLK0 | **100 MHz**（时序收敛：WNS +0.336 ns，0 失败端点） |
| 卷积数据类型 | `ap_fixed<16,7, AP_RND, AP_SAT>`，外部整型缩放 `SCALE = 512` |
| 源码中的时钟配置 | `src/vivado/system_bd.tcl` 已设 `PCW_FPGA0_PERIPHERAL_FREQMHZ=100`；重建需同步重编 FSBL（见 §6） |

## 2. 资源占用（实现后，Vivado 官方报告）

| 资源 | 使用量 | 可用量 | 利用率 |
|---|---|---|---|
| Slice LUTs | 43,980 | 53,200 | **82.67%** |
| LUT as Logic | 35,873 | 53,200 | 67.43% |
| Slice Registers (FF) | 42,901 | 106,400 | 40.32% |
| Block RAM Tile | 94.5 | 140 | **67.50%** |
| DSP48 | 218 | 220 | **99.09%** |
| 功耗（Total On-Chip） | **2.953 W** | — | 动态 2.753 W + 静态 0.200 W（100 MHz，Vivado 估算） |

> DSP 使用率 99.09% 是当前性能的**硬瓶颈**：进一步提速需要算法级改动（如 int8 量化、Winograd 或降低输入分辨率）。

## 3. 时序结果（Vivado 官方报告）

| 指标 | 值 |
|---|---|
| 约束时钟 | `clk_fpga_0`，周期 **10.000 ns（100.000 MHz）** |
| **WNS（Setup）** | **+0.336 ns**（收敛） |
| **TNS** | **0 ns** |
| **失败端点** | **0**（Setup）；Hold 0 失败（WHS = +0.034 ns） |
| HLS 目标时钟 | 10 ns（100 MHz） |

**结论**：100 MHz 实现时序收敛（WNS **+0.336 ns**、TNS 0、0 失败端点）；板端实测 **496.6 ms/帧、2.01 FPS**，1899 条关键点记录稳定可复现。

## 3.1 原始报告文件（`build/reports/`）

| 文件 | 内容 |
|---|---|
| `utilization_routed.rpt` | 100 MHz 实现后资源占用（上表数据来源） |
| `timing_summary_routed.rpt` | 布线后时序汇总（WNS/TNS/失败端点） |
| `power_routed.rpt` | 功耗估算 |
| `clock_utilization_routed.rpt` | 时钟资源使用 |
| `drc_routed.rpt` / `route_status.rpt` | DRC 与布线状态 |

## 4. 性能实测

| 指标 | 值 | 说明 |
|---|---|---|
| 单帧推理 | **496.6 ms** | `forward()` 全程（含 PL→PS 数据传输），A4C 54 帧实测 |
| 吞吐 | **2.01 FPS** | 100 MHz 时钟 |
| 峰值算力 | **43.6 GOPS** | 218 DSP × 2 × 100 MHz |
| ARM 关键点后处理 | **2.0 ms/帧** | 每类 top-1 + sigmoid 解码，约 91k MAC |
| 串口输出开销 | ≈ 90 ms/帧 | 36 行文本 @115200；可关闭 |
| SD 写盘（旧版本） | ≈ 40~90 ms/帧 | 新版本已取消 out 文件写盘，改为串口输出 |

## 5. 构建步骤（可复现）

### 5.1 HLS
```
打开 src/hls（Vivado HLS 2018.3）→ C 综合 → 导出 IP
关键配置：
  - 顶层函数：conv/std_conv/pwconv/maxpool/upsample
  - 数据类型：ap_fixed<16,7,AP_RND,AP_SAT>
  - 输出缩放：SCALE=512（整型输出 = round(float*512)）
  - 目标时钟：10 ns
```

### 5.2 Vivado
```
打开 src/vivado/project.xpr（或由 src/vivado/system_bd.tcl 重建 Block Design）
Block Design：Zynq PS7 + conv IP + AXI DMA/HP + proc_sys_reset
  - FCLK0：100 MHz（时序已收敛，WNS +0.336 ns）
综合 → 实现 → 生成 bitstream
导出 hw platform（含 system_wrapper.bit + ps7_init.tcl）
```

### 5.3 SDK（应用 + BOOT.bin）
```
build/build_bsp_and_app.tcl  → 重新生成 BSP 并编译应用（源码 src/software）
产物：board/bitstream/yolov4_tiny.elf
BOOT.bin：FSBL + bitstream + application（board/boot.bif 为现成模板）
```

### 5.4 权重准备（BN 折叠，PC 端）
```
PyTorch 权重（Oct-20 版本）→ BN 折叠：
  W' = W·γ/√(σ²+ε);  b' = (b−μ)·γ/√(σ²+ε)+β
→ 按层导出 float32 权重 → 板端 ARM 读入后 ×512 转 int16（SCALE=512）
输出：weights/sd_weights_oct20/（42 个文件）
```

## 6. 优化过程记录（前后对比）

| 阶段 | 改动 | 效果 |
|---|---|---|
| 原始工程 | HLS 卷积 + PS 调度，逐层打印 + 写 out 文件 | 基线：结果需回 PC 逐层解码 |
| + ARM 关键点后处理 | 在 `debug.cpp` 中实现每类 top-1 + sigmoid 解码 + 归一化坐标 | 板端直出 36 点，**+2.0 ms**，无需 out 文件 |
| + 去掉 out 写盘 | 每帧不再写 415 KB×2 | 单帧循环时间 −40~90 ms |
| + SD/FatFS 修复 | `fopen`→`f_open`；`SD_Init` 提前；缺文件保护 | 消除板端"读空图算垃圾点" |
| + 归一化坐标输出 | 不再写死 670×573 | 任意分辨率图片可直接测试 |
| + 可变帧数 | 读取 `yolo_test/img_num.txt` | 1~200 张任意测试集 |

精度方面：板端（int16 定点）与 PC（float32）对比：关键点位置 96.7% ≤2 px、GT 命中率差 2~4 个百分点，量化损失在可接受范围。

## 7. 新规则实测精度（2026-10-29）

| 项 | 值 |
|---|---|
| 固件解码规则 | 每框取 36 类 argmax 作为该框类别，再按类保留最高分（与 PC 参考 `yolo2.py` 一致） |
| 板端 GT 命中（A4C 54 帧 / 1944 点，容差约 11 px） | **79.12%（1538/1944）** |
| PC float 参考 | 77.88% |
| 逐点误差 | 中位 5.85 px，平均 7.01 px，90 分位 13.74 px |
| 每帧命中 | 平均 28.5 / 36（最好 35，最差 21） |
| 弱类 | cls28(39%)、cls31(43%)、cls29(50%)、cls6/16(56%) |
| 证据 | `board/logs/log_toshiba_a4c_54f_100mhz.txt`；指标 CSV 见 `sim/results/` |

> 注意：片上功耗 2.953 W 为 Vivado vectorless 估算；板级功耗需按 `board/README.md` 第 8 节实测，两者口径不同。

## 8. 最终实现结果（100 MHz）

| 指标 | 值 |
|---|---|
| WNS / TNS | **+0.336 / 0 ns** |
| Setup 失败端点 | **0** |
| 约束时钟 | 10.000 ns / 100.000 MHz |
| Fmax（1/(T−WNS)） | 103.5 MHz |
| 单帧推理（实测） | **496.6 ms** |
| 帧率 | **2.01 FPS** |
| 峰值算力（218×2×f） | 43.6 GOPS |
| 功耗估算 | **2.953 W**（动态 2.753 + 静态 0.200） |
| 能效（峰值算力/估算功耗） | 14.77 GOPS/W |
| 关键点输出 | 1899 条 K 行（A4C 54 帧） |

报告原文：`reports/timing_summary_routed.rpt`、`reports/power_routed.rpt`、`reports/utilization_routed.rpt`、
`reports/clock_utilization_routed.rpt`、`reports/drc_routed.rpt`。
