# 验证与仿真（Verification / Simulation）

本目录记录功能正确性如何被确认。**所有评测脚本使用包内相对路径，无需任何外部工程即可复跑**。

## 1. 验证策略（5 个层次）

| 层次 | 验证内容 | 方法 | 结果 | 包内可复跑 |
|---|---|---|---|---|
| L1 权重一致性 | SD 卡 int16 权重是否来自训练权重的 BN 折叠 | 逐层反量化对比 | 相关系数 1.000000 | `scripts/legacy/check_weight_identity.py`（需设置路径） |
| L2 量化仿真 | int16 定点量化本身的误差 | Python 仿真（截断/舍入、SCALE 512/1024） | 唯一位置 28.6~28.8 vs float32 28.8 | `scripts/legacy/quantization_sim.py`（需设置路径） |
| L3 板端 vs PC | 同一输入下关键点差异 | 逐点对比 | 96.7% ≤2 px（中位 0.31 px） | 需归档的演示集数据（不在包内） |
| L4 GT 精度 | 板端/PС 与人工标注的命中率 | 逐帧逐类命中统计 | 板端 73.87% / 66.50%；PC 77.88% / 68.72% | ✅ `scripts/eval_board_gt.py`、`scripts/eval_pc_gt.py` |
| L5 运行确定性 | 断电重启后结果是否一致 | 两次运行日志逐帧对比 | 差 0 | ✅ `scripts/generate_validation_results.py` |

## 2. 脚本清单（`scripts/`）

| 脚本 | 作用 | 依赖 |
|---|---|---|
| `paths.py` | 包内相对路径常量 + 路径自检 | 无 |
| `eval_board_gt.py` | 板端结果 GT 命中率（两组数据）| numpy、pillow |
| `eval_pc_gt.py` | PC PyTorch 参考精度（两组数据）| numpy、pillow、torch + `sim/pc_reference/` |
| `generate_validation_results.py` | 一键重算 `results/` 下全部 CSV | numpy、pillow |
| `legacy/*.py` | 早期分析脚本（含作者机器绝对路径，仅历史参考，不建议直接运行） | — |

## 3. 复跑方式（包内自包含）

```bash
# 0) 环境检查
python sim/scripts/paths.py
# 期望：all paths ok: True

# 1) 板端结果评测（不需要 torch）
python sim/scripts/eval_board_gt.py --set both
# 期望（legacy 旧解码规则日志）：philips 66.50% (1197/1800)、toshiba 73.87% (1436/1944)

# 2) PC 参考评测（需要 torch，CPU 即可）
python sim/scripts/eval_pc_gt.py --set both
# 期望：philips 68.72% (1237/1800)、toshiba 77.88% (1514/1944)

# 3) 重算全部验证 CSV
python sim/scripts/generate_validation_results.py
# 期望（legacy）：66.50% / 73.87%，determinism 差分 0

# 4) 新规则板端日志评测（不需要 torch）
python board/scripts/eval_serial_vs_gt.py board/logs/log_toshiba_a4c_54f_newrule.txt data/images_toshiba_a4c data/labels_toshiba_a4c
# 期望：1538/1944 = 79.12%
```

依赖版本见根目录 `ENVIRONMENT.md`；PC 端需要 `numpy`、`pillow`，只有 `eval_pc_gt.py` 需要 `torch`。
模型代码与 anchors 在 `sim/pc_reference/`，权重在 `data/weights/`，不需要原始训练工程。

## 4. 结果文件（`results/`）

| 文件 | 内容 |
|---|---|
| `summary_metrics.csv` | 两组数据的板端/PC 命中率、置信度、单帧耗时 |
| `board_philips_per_frame.csv` / `board_toshiba_per_frame.csv` | 板端逐帧：检测位置数、GT 点数、命中数、平均 conf |
| `per_class_board_philips.csv` / `per_class_board_toshiba.csv` | 板端逐类命中率 |
| `per_frame_pc_philips.csv` / `per_frame_pc_toshiba.csv` | PC 参考逐帧统计 |
| `determinism_powercycle.csv` | 两次断电重启逐帧 conf 差 / 位置差（全为 0） |

## 5. 关键结论

1. 量化损失可控：板端相对 PC 的 GT 命中率低 2~4 个百分点；部分类别板端甚至优于 PC。
2. 确定性成立：两次断电重启结果逐帧一致（置信度差 0、位置差 0）。
3. 唯一隐患：时序负 slack（WNS −0.921 ns），建议重建时把 FCLK 降到 100 MHz。

## 6. 新规则评测结果（2026-10-29）

| 文件 | 内容 |
|---|---|
| `results/board_newrule_a4c_per_frame.csv` | 新规则 A4C 54 帧逐帧（位置数/命中/conf） |
| `results/per_class_board_newrule_a4c.csv` | 新规则逐类命中率 |
| `results/summary_metrics.csv` | 新增行 `toshiba_a4c_normal_54f_newrule`：79.12%（旧行标记 legacy） |
| `data/reference_results/` | 同两份 CSV 的副本 |

结论：解码规则修复后板端从 73.87% 提升到 **79.12%**（+5.25 pp），已与 PC float（77.88%）持平/略高；
瓶颈已从"部署/解码"转到"模型本身"（弱类 cls28/31/29/6/16）。
