# Build Guide（可复现构建说明）

本目录提供从源码到可运行产物的完整构建路径。工具链：**Vivado / SDK 2018.3**。

## 文件

| 文件 | 用途 |
|---|---|
| `build_bsp_and_app.tcl` | 重新生成 BSP 并编译 PS 端应用（xsdk -batch -source） |
| `implementation_report.md` | 综合实现报告：资源、时序、功耗、性能（含官方报告关键数据） |
| `reports/` | Vivado 官方报告原文（资源/时序/功耗/DRC/布线状态） |

## 1. HLS 综合

```tcl
# Vivado HLS 2018.3（在包根目录执行）
open_project src/hls
open_solution solution1
set_part xc7z020clg400-1
create_clock -period 10 -name default
csynth_design
export_design -format ip_catalog
```

关键点：
- 数据类型 `ap_fixed<16,7,AP_RND,AP_SAT>`（`src/hls/std_conv.h`）
- 输出整型缩放 `SCALE = 512`
- 顶层：`conv`（标准卷积）、`pwconv`（逐点卷积）、`maxpool`、`upsample`

## 2. Vivado 工程

```
1) 打开 src/vivado/project.xpr（或按 src/vivado/system_bd.tcl 重建 BD）
2) Block Design 组成：
   Zynq PS7 (FCLK0) ── AXI-Lite(控制) ── 卷积 IP
                    ── AXI-HP(数据) ── DMA/内存
3) 时钟：FCLK0 = 100 MHz（收敛版，WNS=+0.336ns；120 MHz 版 WNS=-0.921ns，仅作对比）
4) 综合 → 实现 → 生成 bitstream
5) Export Hardware（含 system_wrapper.bit + ps7_init.tcl）
```

## 3. SDK 应用与 BOOT.bin

> **改频率时注意**：`src/vivado/system_bd.tcl` 里 FCLK0 已设为 100 MHz。改 FCLK 后必须从新实现导出 HDF，
> 替换 hw platform 的 `ps7_init.c/h/tcl` 并**重新编译 FSBL**，再重打 BOOT.bin；否则 Zynq 的 FCLK 仍按旧 FSBL 配置运行
> （只换位流会出现"假降频"）。


> 包内 `src/software/xilinx.spec` 是小写文件名；在 SDK 工程中使用时复制为 `Xilinx.spec`
> （链接参数 `-specs=Xilinx.spec` 需要该文件名），属工具链运行时约束。

```bash
# 生成 BSP + 编译应用（产物：yolov4_tiny.elf）
C:\Xilinx\SDK\2018.3\bin\xsdk.bat -batch -source build_bsp_and_app.tcl
```

BOOT.bin 组成（模板见 `board/boot.bif`，包内相对路径，在包根目录执行）：
```
C:\Xilinx\SDK\2018.3\bin\bootgen.bat -image board/boot.bif -arch zynq -o BOOT.bin -w on
# 再把 BOOT.bin 打包为 board/sd_boot_image.zip（包内不单独存放大写 BOOT.bin）
```
```
zynq_fsbl.elf + system_wrapper.bit + yolov4_tiny.elf
```

## 4. 权重（PC 端 BN 折叠）

```
PyTorch 权重 (Oct-20) → BN folding → 逐层 float32 导出
  W' = W·γ/√(σ²+ε)
  b' = (b−μ)·γ/√(σ²+ε)+β
→ SD 卡 yolov4_tiny_weights/（42 个文件）
```

板端读取后按 `SCALE=512` 量化为 int16。

## 5. SD 卡镜像布局

```
<SD 根目录>/
├─ BOOT.bin
├─ yolov4_tiny_weights/        # 42 个 int16 权重文件
└─ yolo_test/
   ├─ img0.bin ... imgN.bin    # 416x416x3 float32 (RGB/255, CHW)
   ├─ img0.png ... imgN.png    # 对应原图（供出图用）
   └─ img_num.txt              # 图片张数（1~200）
```

编码脚本：`board/scripts/encode_images.py`（或直接跑 `board/scripts/prepare_sd_card.bat`）

## 6. 验证构建成功

```
① 板端串口：image num = N；每帧 KP i 36/36；最后 ALL DONE N frames
② 推理耗时 ≈ 496.6 ms/帧（100 MHz）
③ 用 sim/scripts/ 下脚本核对板端 vs PC 关键点一致性
```

## 7. 复现结果核对（与 `build/reports/` 同一位流）

| 指标 | 值 |
|---|---|
| 板端 GT 命中率（新规则，TOSHIBA A4C 54 帧） | **79.12%**（1538/1944） |
| PC float 参考 | 77.88% |
| 单帧耗时（100 MHz） | 496.6 ms |
| WNS（100 MHz） | **+0.336 ns，0 失败端点**（120 MHz 版 −0.921 ns/61 端点见 `reports/historical_120mhz/`） |
| 片上功耗估算 | 2.953 W（动态 2.753 + 静态 0.200） |
| 板级功耗 | **待实测**（测量步骤见 `board/README.md` 第 8 节） |

## 8. 时序/功耗报告复测（批处理，不打开 GUI）

包内提供 `build/rerun_reports.tcl`：重新打开同一实现（`impl_1`）重跑报告。

```bat
C:\Xilinx\Vivado\2018.3\bin\vivado.bat -mode batch -notrace ^
  -source build\rerun_reports.tcl -tclargs D:\out_reports
```

> 该命令为 **批处理模式**，不会弹出 Vivado 窗口；运行日志写入当前目录的 `vivado.log` / `vivado.jou`。
> 脚本里的工程路径默认指向 `D:/fpga_work/yolov4_tiny/...`，换机器时改第一行 `set XPR`。

（该命令复测的是 120 MHz 历史版，结果与原始报告一致：WNS −0.921 ns / 61 失败端点，报告在 `reports/historical_120mhz/`。）

交付版为 **100 MHz 收敛版**（WNS +0.336 ns、0 失败端点），报告见 `reports/timing_summary_routed.rpt` 等。