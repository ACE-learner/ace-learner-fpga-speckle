# 校验脚本（Validation Scripts）

> 技能包第 ③ 项：可自动复用的校验脚本。目标：**陌生队伍拿到本目录，能直接验证自己的工程是否可复现、指标是否达标**。

## 1. `check_package.py` —— 工程包自检（本工程用）

一键检查：
- 目录结构是否符合约定（src/sim/build/board/data/skill/report）
- 关键产物是否存在（源码、位流、BOOT.bin、报告、日志）
- 源码关键标记（`ap_fixed<16,7>`、`SCALE=512`、FatFS `f_open`、`ALL DONE` 结束标记）
- 数据完整性（图片/GT 数量）
- 日志完整性（帧数、36/36、结束标记）
- 指标是否在预期区间（GT 命中率、单帧耗时）

```bash
python check_package.py [package_root]
# 退出码 0 = 全部通过；1 = 有失败项（会打印失败清单）
```

**已验证效果**：本提交包跑一次约 1 秒，覆盖 40+ 项检查，可作提交前最后一道闸。

**失效条件**：如果题目没有 GT 或没有串口日志，第 4/5/6 项需按实际情况裁剪。

## 2. 与本包其他脚本的关系

| 需求 | 脚本 |
|---|---|
| 权重是否就是训练权重的折叠结果 | `../../sim/scripts/check_weight_identity.py` |
| 量化误差有多大 | `../../sim/scripts/quantization_sim.py` |
| 板端与 PC 关键点逐点对比 | `../../sim/scripts/compare_board_vs_pc.py` |
| GT 命中率（板端/PC） | `../../sim/scripts/eval_board_gt.py`、`eval_pc_gt.py` |
| 断电重启确定性 | `../../sim/scripts/determinism_check.py` |
| 串口日志抓取（防残留） | `../../board/scripts/read_serial.ps1` |

## 3. 复用建议（换到别的题目）

1. 复制 `check_package.py` 作为骨架；
2. 改三处：目录白名单（第 1 节）、关键产物清单（第 2 节）、指标区间（第 6 节）；
3. 在 CI/提交前跑一次，失败即阻断。

**来源**：本工程曾因"结果文件是旧的"和"权重版本不对"两次误判精度，因此把"批次/哈希/帧数校验"固化成脚本。
