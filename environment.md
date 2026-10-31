# 环境与版本要求（Environment & Versions）

> 本文件说明复现本工程所需的环境、依赖版本，以及"哪些脚本依赖什么"。
> 所有版本号均为**实测验证过的组合**；未验证的组合请参考括号内的最低版本要求。

## 1. 版本矩阵

| 组件 | 用途 | 实测版本 | 最低要求 | 说明 |
|---|---|---|---|---|
| Windows | 构建/板端工具链 | Windows 10/11 64 位 | Windows 10 | bat/ps1 脚本按 Windows 编写 |
| Vivado | 位流综合/实现 | 2018.3 | 2018.3 | 工程文件为 2018.3 格式，高版本需升级工程 |
| Xilinx SDK | BSP/应用/BOOT.bin | 2018.3 | 2018.3 | `build/build_bsp_and_app.tcl` 用 xsdk 调用 |
| Python（PC 端） | 编码/渲染/评测 | **3.13.16** | 3.8 | 脚本含 f-string（3.6+）；推荐 3.10~3.13 |
| numpy | 数值计算 | **2.5.2** | 1.20 | 使用 `np.random.default_rng`（1.17+） |
| Pillow | 图片读写/绘制 | **12.3.0** | 8.0 | `ImageFont.truetype` 需字体文件（缺失时自动回退） |
| PyTorch | PC 参考评测（可选） | **2.15.0.dev+cu130**（CPU 推理） | 1.8 | 仅 `eval_pc_gt.py` 需要；CPU 版本即可 |
| PYNQ | 通用 PYNQ 技能（可选） | 未在本包实机验证 | 2.5 | 需与板卡匹配的 PYNQ 镜像；脚本已兼容 2.5~3.x 的 Buffer API |

## 2. 按用途分组的依赖

### A. 板端运行（不需要 PC Python）
- Vivado/SDK 2018.3（重建时才需要）
- SD 卡（FAT32）、JTAG 线（FTDI 0403:6014）、USB-UART（CH340，115200-8-N-1）
- 运行时不需要 Python

### B. PC 端编码与渲染（最常用）
```bash
pip install numpy pillow
python board/scripts/encode_images.py <图片目录> <SD卡:\yolo_test>
python board/scripts/render_from_serial.py <串口日志> <图片目录> <输出目录>
```
实测：Python 3.13.16 + numpy 2.5.2 + Pillow 12.3.0。

### C. PC 端精度评测（板端 vs PC）
```bash
pip install numpy pillow
# 板端结果评测（不需要 torch）
python sim/scripts/eval_board_gt.py --set both

# PC 参考评测（需要 torch，CPU 即可）
pip install torch --index-url https://download.pytorch.org/whl/cpu
python sim/scripts/eval_pc_gt.py --set both
```
模型代码与 anchors 已随包提供：`sim/pc_reference/`；权重：`data/weights/logs_1019_best_epoch_weights.pth`。

### D. 验证结果重新生成
```bash
python sim/scripts/generate_validation_results.py
```
一键重算 `sim/results/` 下全部 CSV（板端 GT 命中率、逐帧统计、断电重启一致性）。

### E. PYNQ 技能包（可选，需 PYNQ 板）
```bash
pip install numpy          # 板端通常自带
python skill/pynq/03_env_and_offline_deploy/check_env.py
```

## 3. 已验证的复现结果（用于核对环境是否装对）

| 命令 | 期望输出 |
|---|---|
| `python sim/scripts/paths.py` | `all paths ok: True` |
| `python sim/scripts/generate_validation_results.py` | Philips 66.50%、Toshiba 73.87%、determinism 差分 0 |
| `python sim/scripts/eval_board_gt.py` | 66.50% / 73.87%（legacy 旧解码规则日志） |
| `python board/scripts/eval_serial_vs_gt.py board/logs/log_toshiba_a4c_54f_newrule.txt data/images_toshiba_a4c data/labels_toshiba_a4c` | 1538/1944 = **79.12%**（新规则） |
| `python sim/scripts/eval_pc_gt.py --set both` | 68.72% / 77.88% |
| `python skill/validation/check_package.py` | `51+ checks, 0 failed` |

## 4. 已知限制

1. `sim/scripts/legacy/` 下的脚本来自早期分析，**含作者机器绝对路径**（`D:\...`），仅供历史参考，不建议直接运行。
2. `board/scripts/` 下脚本已全部改为**包内相对路径**（2026-10-29），无需替换路径；`sim/scripts/legacy/` 仍为历史脚本。
3. 板端脚本依赖 Windows PowerShell 5.1（`read_serial.ps1` 用了 `System.IO.Ports`，不支持 PowerShell Core 的某些分支）。
4. 未验证：Python 3.7 及以下（脚本用了 f-string 之外无高级语法，理论上可用但未实测）。
5. PYNQ 技能脚本只做了离线逻辑验证，未在 PYNQ 实机运行。
6. SD 拨码启动路径需在目标板上再验一次（JTAG 路径已实机验证）；板级功耗尚未实测（步骤见 `board/README.md` 第 8 节）。
