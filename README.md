# FPGA Speckle Keypoint Detector

Zynq-7020 上的超声心肌散斑 **36 关键点**检测系统（2026 嵌入式芯片与系统设计竞赛，AMD 赛道）。

- 模型：YOLOv4-Tiny（36 类，416×416 输入）
- 硬件：Zynq-7020（PL 卷积加速器 + PS 推理调度/关键点后处理）
- 最终交付：**100 MHz** 位流，WNS **+0.336 ns**、TNS 0、0 失败端点
- 速度：**496.6 ms/帧（约 2.0 FPS）**，ARM 后处理 **2.0 ms**
- 能效：峰值算力 **43.6 GOPS**，约 **14.77 GOPS/W**
- 精度：TOSHIBA A4C 54 帧板端 GT 命中 **79.12%**（PC 浮点 77.88%），
  Siemens A4C rca 56 帧板端 GT 命中 **77.48%**

---

## 1. 系统结构

```
 PC(Windows) ──① 图片编码写 SD 卡 ──▶ SD 卡 ──② 插板启动 ──▶ Zynq-7020
     ▲                                                          │
     │                                   PL: HLS 卷积加速器(conv/pwconv/maxpool/upsample)
     │                                   PS: 读图 → 逐层调度 PL → 关键点后处理
     │                                                          │
     └────────── ③ 串口 115200 接收 K 行（36 类归一化坐标）◀────┘
```

- 输入：`yolo_test/img*.bin` = 416×416×3 float32（RGB/255，CHW）
- 权重：`yolov4_tiny_weights/` = BN 折叠后的 42 个 float32 文件（板端载入时按 `SCALE=512` 转 int16）
- 输出：每帧 `KPT` / `KP` / `K` 行（K 行为 36 类归一化坐标与置信度）
- 全离线运行，不需要网络，跑完不需拔卡

## 2. 目录结构

| 目录 | 内容 |
|---|---|
| `src/hls/` | HLS C++ 源码（卷积/逐点卷积/池化/上采样 + 定点类型） |
| `src/rtl/` | HLS 导出的 Verilog RTL 与综合报告 |
| `src/software/` | PS 端 C++ 源码（调度、SD 读写、关键点后处理） |
| `src/vivado/` | Vivado Block Design tcl、约束、xpr |
| `sim/` | 验证脚本与结果 CSV；PC 参考推理代码在 `sim/pc_reference/` |
| `build/` | 可复现构建脚本 + 综合/实现报告（资源、时序、功耗） |
| `board/` | 位流、BOOT.bin、ELF、运行脚本、**最终实测日志**、结果示例 |
| `data/` | 测试序列（图像 + GT 标签）与参考结果；数据集说明见 `data/README_siemens_a4c_rca.md` |
| `skill/` | 技能包：工作流、提示词、踩坑记录、证据索引、自检脚本 |
| `report/` | 设计报告与模型协作记录 |
| `environment.md` | 环境版本矩阵与复现核对表 |

## 3. 数据集

完整数据集来自百度网盘（约 **0.75 GB / 12,491 个文件**，7 个厂商 × A2C/A3C/A4C × 5 个切面），
体积过大，不适合直接放进普通 Git 仓库。仓库内置**复现报告与板端测试实际用到的子集**：

| 序列 | 位置 | 帧数 | 说明 |
|---|---|---|---|
| Siemens A4C / rca | `data/images_siemens_a4c_rca`、`data/labels_siemens_a4c_rca` | 56 | 新增，含 SHA256 清单 |
| TOSHIBA A4C | `data/images_toshiba_a4c`、`data/labels_toshiba_a4c` | 54 | 报告主测试集 |
| Philips A3C | `data/images_philips_a3c`、`data/labels_philips_a3c` | 50 | 早期对照序列 |

命名约定：图像 `img<N>.png`，标签 `g<N>.txt`（`cls cx cy w h`，归一化）。
Siemens 原始文件名 `0001.png`/`0001.txt` → `img0.png`/`g0.txt` 的映射见 `data/README_siemens_a4c_rca.md`。

> 完整数据集如需公开，建议使用 **GitHub Release 压缩包**或 **Git LFS**，不要直接提交进普通 Git 历史。

## 4. 快速复现

### 路径 A：SD 卡直接启动（不需要 Vivado，最快）

1. SD 卡格式化为 FAT32；
2. 双击 `board/scripts/prepare_sd_card.bat`，按提示选择：
   - 测试图片目录：`data/images_toshiba_a4c`（54 帧）或 `data/images_siemens_a4c_rca`（56 帧）；
   - SD 卡盘符；
3. 板子 BOOT 拨到 SD，插卡上电；
4. 串口 115200 应看到（以 TOSHIBA 54 帧为例）：

```
Yolo4 Tiny Test
image num = 54
KPT 0 2007
KP 0 36/36
K 0 0 0.76 0.86 ...
ALL DONE 54 frames
```

### 路径 B：JTAG 下载运行（需要 Vivado/SDK 2018.3）

```bat
C:\Xilinx\SDK\2018.3\bin\xsct.bat board\scripts\run_on_board.tcl
```

流程：`connect → rst -system → fpga -file bit → ps7_init → dow elf → con`。

### 路径 C：从源码重建

见 `build/README.md`：HLS 综合/导出 IP → Vivado 综合实现 → SDK 编译 FSBL/APP → BOOT.bin。

## 5. PC 端工具

```bash
# 编码任意图片目录（png/jpg/bmp），按自然顺序输出 img*.bin/png 与 img_num.txt
python board/scripts/encode_images.py <图片目录> <输出目录> 200

# 用串口日志 + 原图渲染关键点
python board/scripts/render_from_serial.py <串口日志> <图片目录> <输出目录>

# 串口日志 vs GT 命中率（标签按 g0.txt… 命名）
python board/scripts/eval_serial_vs_gt.py <串口日志> <图片目录> <标签目录>
```

`render_results.ps1` 会自动记住/询问图片目录，并支持 `0001.png` 等任意命名。

## 6. 复现验证清单

| 检查项 | 期望值 | 实测 |
|---|---|---|
| 推理耗时（100 MHz） | ≈ 496.6 ms/帧 | 496.54 / 496.60 ms |
| 每帧关键点类别数 | 33–36（均值 35.2） | `KP 36/36` 27/54 帧 |
| 板端平均置信度 | ≈ 0.46 | 0.459（A4C 100 MHz） |
| ARM 后处理耗时 | < 3 ms | 2.0 ms |
| TOSHIBA A4C GT 命中率 | ≈ 79.1% | **79.12%**（1538/1944） |
| Siemens A4C rca GT 命中率 | — | **77.48%**（1562/2016，56 帧） |
| 资源占用 | LUT 82.67%、DSP 99.09% | 43 980 LUT / 218 DSP |
| 时序 | WNS > 0、0 失败端点 | +0.336 ns / 0 |
| 功耗（Vivado 估算） | ≈ 2.95 W | 2.953 W（动态 2.753 + 静态 0.200） |
| 技能包自检 | 全部通过 | `python skill/validation/check_skill.py` |
| 工程包自检 | 全部通过 | `python skill/validation/check_package.py` |

## 7. 硬件与软件环境

| 项 | 要求 |
|---|---|
| 开发板 | Zynq-7020（XC7Z020），SD 卡槽、JTAG、USB-UART |
| SD 卡 | FAT32，≥ 1 GB |
| JTAG | FTDI 线（USB `0403:6014`） |
| 串口 | CH340（USB `1A86:7523`），115200-8-N-1 |
| Vivado / SDK | 2018.3（仅重建需要） |
| PC Python | 3.8+；`numpy`、`pillow`（PC 参考评测另需 CPU 版 torch） |

详细版本矩阵见 `environment.md`。

## 8. 已知限制

1. 输入为静态图片序列，不是实时视频流；
2. 串口打印 36 行/帧约耗时 90 ms，可把 `KP_PRINT` 置 0 关闭；
3. 权重必须使用 Oct-20 版（BN 折叠 int16），其他 checkpoint 精度下降；
4. 板级功耗尚未实测，2.953 W 为 Vivado 片上估算；
5. SD 拨码启动路径需在目标板上再验证一次（JTAG 路径已实机验证）；
6. PYNQ 技能包只做了离线自检，未在 PYNQ 实机验证。

## 9. 仓库整洁说明

- 保留最终结果与验证必需的日志：TOSHIBA/Siemens 100 MHz 日志、确定性复跑 `log_powercycle_round1/2.txt`、Philips 对照日志；
- 已删除旧 120 MHz 日志（`log_toshiba_a4c_54f.txt`）和重复串口日志（`serial_20261102_145526.txt`）；
- `board/results/` 只保留 1 张最终结果示例，运行生成的 `render_*` 目录已加入 `.gitignore`；
- 测试图片、标签、SHA256 清单随仓库提供；完整数据集不入 Git。

## 10. 版权与致谢

- YOLOv4-Tiny 训练与 PC 推理基于开源 PyTorch 实现；
- 超声数据集版权归原发布方，本仓库仅保留复现所需子集，不含患者身份信息；
  仅用于竞赛复现与学术研究，不得用于临床诊断或商业用途；
- 本工程补充了 PS 端关键点后处理、SD/FatFS 修复、归一化坐标输出与验证工具链。

## 11. 提交结构对照（选题指南 3.3.5）

| 指南要求 | 本仓库位置 |
|---|---|
| 完整工程文件与源码 | `src/` |
| 仿真或验证结果 | `sim/` |
| 综合与实现报告 | `build/` |
| 上板工程 / 运行脚本 / 实测输出 / 参考比对 | `board/` |
| 可复现构建脚本 | `build/` + `board/scripts/` |
| 技能包 | `skill/` |
| 设计报告 | `report/` |
| 数据集 | `data/`（子集） |
