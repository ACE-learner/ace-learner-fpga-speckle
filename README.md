# FPGA Speckle Keypoint Detector (2026 Embedded Chip & System Design Contest, AMD track)

基于 Zynq-7020 的**超声心肌散斑 36 关键点检测**硬件加速工程。

- 模型：YOLOv4-Tiny（36 类，每类对应一个关键点，416×416 输入）
- 硬件：Zynq-7020（PL 实现卷积加速器 + PS 运行推理调度与关键点后处理）
- 性能：**496.6 ms/帧（2.01 FPS）**，ARM 关键点后处理 **2.0 ms**；峰值算力 43.6 GOPS、能效 14.77 GOPS/W
- 精度（GT 命口径，容差约 11 px；板端 vs PC PyTorch）：
  - TOSHIBA A4C 54 帧：**79.12%** vs 77.88%
- 关键点一致性：板端与 PC 的 36 个关键点中 **96.7% 位置误差 ≤ 2 px**（中位 0.31 px）

---

## 1. 系统结构

```
 PC(Windows) ──① 编码图片写 SD 卡 ──▶ SD 卡 ──② 插板子 ──▶ Zynq-7020
     ▲                                                        │
     │                                       PL: HLS 卷积加速器(conv/pwconv/maxpool/upsample)
     │                                       PS: 读图 → 逐层调度 PL → 关键点后处理
     │                                                        │
     └────────── ③ 串口 115200 接收 36 个关键点（归一化坐标）◀──┘
```

- **输入**：`yolo_test/imgN.bin` = 416×416×3 float32（RGB/255，CHW 布局）
- **权重**：`yolov4_tiny_weights/` = BN 折叠后的 int16 定点（42 个文件，22.7 MB）
- **输出**：每帧 36 行 `K <frame> <cls> <nx> <ny> <nw> <nh> <score>`（归一化坐标 0~1）
- **不需要网络**；结果通过串口输出，跑完不需拔卡

---

## 2. 目录结构

| 目录 | 内容 |
|---|---|
| `src/hls/` | HLS C++ 源码（卷积/逐点卷积/池化/上采样 + 定点类型定义） |
| `src/rtl/` | HLS 导出的 Verilog RTL 与综合报告（`hls_generated_extra_rtl.zip` 为其余自动生成子模块） |
| `src/software/` | PS 端 C++ 源码（调度、SD 读写、关键点后处理） |
| `src/vivado/` | Vivado 工程文件（Block Design tcl、约束、xpr） |
| `sim/` | 验证脚本与结果（板端 GT、PC 参考、确定性、一键重算 CSV）；模型推理代码在 `sim/pc_reference/` |
| `environment.md` | 环境与版本要求（含实测版本矩阵、按用途分组的依赖、复现核对表） |
| `requirements.txt` | PC 端 Python 依赖（numpy、pillow；torch 可选，CPU 版即可） |
| `build/` | 可复现构建脚本 + 综合实现报告（资源/时序/功耗） |
| `board/` | 板端工程：位流、BOOT.bin、ELF、运行脚本（`board/scripts/`，全部相对路径）、实测日志、结果图 |
| `data/` | 测试数据（两组序列的图片 + GT 标签）与参考结果 |
| `skill/` | 技能包 v1.1：总览 + 机器清单（skill.json）+ 工作流 + 8 组提示词 + 6 份案例模板 + 18 条踩坑 + 证据索引 + 自检脚本 + 通用 PYNQ 技能 |
| `report/` | 设计报告 + 大模型协作记录 |

---

## 3. 快速复现

### 路径 A：SD 卡直接启动（不需要 Vivado，最快）

1. SD 卡格式化为 FAT32
2. 直接双击 `board/scripts/prepare_sd_card.bat`（自动写 BOOT.bin + 权重 + 测试集），或手动拷贝到卡根目录：
   - 解压 `board/weights/sd_weights_oct20.zip` → 得到 `yolov4_tiny_weights/`（42 个 int16 权重文件）
   - 解压 `board/sd_boot_image.zip` → 得到 `BOOT.bin`（Zynq 启动镜像，**文件名必须大写**）
   - `data/images_philips_a3c/img*.bin`（示例已编码 50 帧；也可直接跑 `board/scripts/prepare_sd_card.bat` 自动写卡）→ 卡内 **`yolo_test/`**
3. 板子 BOOT 切到 SD，插卡上电
4. 串口 115200 应看到：
   ```
   Yolo4 Tiny Test
   image num = 50
   KPT 0 2003 / KP 0 36/36 / K 0 0 0.63 0.74 ...
   ALL DONE 50 frames
   ```

### 路径 B：JTAG 下载运行（需要 Vivado/SDK 2018.3）

```bash
C:\Xilinx\SDK\2018.3\bin\xsct.bat board\scripts\run_on_board.tcl
```

脚本流程：`connect → rst -system → fpga -file bit → ps7_init → dow elf → con`。

### 路径 C：从源码重建（需要 Vivado/SDK 2018.3）

见 `build/README.md`：
```
HLS src → C 综合/导出 IP → Vivado(Block Design) → 综合/实现 → bitstream
        → SDK 编译 FSBL+APP → BOOT.bin → SD 卡
```

### PC 端出图

```bash
python board/scripts/render_from_serial.py <串口日志> <图片目录> <输出目录>
```

---

## 4. 复现验证清单

| 检查项 | 期望值 | 实测 |
|---|---|---|
| 推理耗时（100 MHz） | ≈ 496.6 ms/帧 | 496.54 / 496.60 ms（实测） |
| 每帧关键点类别数 | 33–36（均值 35.2） | `KP 36/36` 27/54 帧；其余 33–35 类 |
| 板端平均置信度 | ≈ 0.46 | 0.459（A4C 100 MHz） |
| ARM 后处理耗时 | < 3 ms | 2.0 ms |
| GT 命中率（TOSHIBA A4C，100 MHz 交付版） | ≈ 79.1% | **79.12%**（1538/1944） |
| 重复运行确定性（同一配置） | 结果一致 | 1899/1899 条 K 行逐位一致 |
| 技能包自检 | 60+ 项全过 | `python skill/validation/check_skill.py`（退出码 0） |
| 工程包自检 | 56 项全过 | `python skill/validation/check_package.py`（退出码 0） |

---

## 5. 硬件与软件环境

详细版本矩阵见 `environment.md`，要点：

| 项 | 要求 |
|---|---|
| 开发板 | Zynq-7020（XC7Z020），SD 卡槽、JTAG、USB-UART |
| SD 卡 | FAT32，≥ 1 GB |
| JTAG | FTDI 线（USB `0403:6014`），路径 B/C 使用 |
| 串口 | CH340（USB `1A86:7523`），115200-8-N-1 |
| Vivado / SDK | 2018.3（仅重建需要） |
| PC Python | 3.8+（实测 3.13.16）；`numpy`、`pillow`；PC 参考评测需 `torch`（CPU 即可） |
| PYNQ（可选） | 2.5+，需与板卡匹配的镜像；见 `skill/pynq/` |

安装依赖：`pip install -r requirements.txt`（torch 可选，装 CPU 版即可）。

---

## 6. 已知限制

1. **时序**：已采用 **100 MHz 收敛版**（WNS +0.336 ns、0 失败端点、功耗估算 2.953 W）。
2. 输入为**静态图片序列**（不是实时视频流）。
3. 串口打印 36 行/帧约耗时 90 ms，可在 `src/software/debug.cpp` 中把 `KP_PRINT` 置 0 关闭。
4. 权重必须使用 **Oct-20 版本**（BN 折叠后 int16，随发布包提供），其他 checkpoint 精度显著下降。
5. **板级功耗尚未实测**：Vivado 的 2.953 W 为片上估算，板级测量步骤见 `board/README.md` 第 8 节。
6. **SD 拨码启动路径**需在目标板上再验证一次（JTAG 路径已实机验证）；若 SD 启动失败可改用 JTAG 路径。
7. **PYNQ 技能包**只做了离线自检（mock 模式），未在 PYNQ 实机验证。

---

## 7. 版权与致谢

- YOLOv4-Tiny 训练与 PC 端推理基于开源 pytorch 实现，权重来自项目原始训练结果。
- 本工程补充了 PS 端关键点后处理、SD/FatFS 修复、归一化坐标输出与验证工具链。

## 8. 提交结构对照（对应选题指南 3.3.5）

| 指南要求 | 本包位置 | 内容 |
|---|---|---|
| 3.3.5.1 完整工程文件与源码 | `src/` | `hls/`（HLS C++ 源）、`rtl/`（HLS 导出 Verilog）、`software/`（PS C++ 源）、`vivado/`（BD tcl / 约束 / xpr） |
| 3.3.5.1 仿真或验证结果 | `sim/` | 验证脚本 + CSV 结果（板端/PC/确定性/新规则）+ `pc_reference/` 模型代码 |
| 3.3.5.1 综合与实现报告 | `build/` | `reports/`（资源/时序/功耗/DRC 原文）+ `implementation_report.md` |
| 3.3.5.1 上板工程/运行脚本/实测输出/参考比对 | `board/` | 位流/BOOT/ELF、`scripts/` 运行脚本、`logs/` 串口日志、`results/` 结果图 |
| 3.3.5.1 可复现构建脚本 | `build/` | `build_bsp_and_app.tcl` + `README.md`（HLS→Vivado→SDK→bootgen 步骤） |
| 3.3.5.2 技能包 | `skill/` | `README.md` + `skill.json` + `workflow.md` + 8 组提示词 + 6 份案例模板 + 18 条踩坑 + `evidence.md` + `validation/check_skill.py` + 通用 PYNQ 技能 |
| 3.3.5.3 设计报告 | `report/` | `design_report.md` + `llm_collaboration_record.md` + `figures/` |
| 3.3.5.4 命名规范 | 全包 | 所有目录/文件名为纯英文小写（字母/数字/下划线/连字符），中文只在文件正文 |


