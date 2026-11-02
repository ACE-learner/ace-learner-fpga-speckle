# 校验脚本（Validation Scripts）

> 技能包第 ③ 项：可自动复用的校验脚本。目标：**陌生队伍拿到本目录，能自己验证技能包是否完整、工程包是否可复现、指标是否达标**。

## 1. `check_skill.py` —— 技能包自检（与具体工程无关，可迁移）

检查：
- 必备文件/目录是否齐全（README/skill.json/workflow/prompts/cases/pitfalls/evidence/changelog/validation/pynq）；
- `skill.json` 是否合法、`entrypoints` 指向的文件是否存在；
- Markdown 相对链接是否可解析（防止"文档写了但文件不存在"）；
- 全部 `.py` 是否可编译；
- 文件/目录命名是否纯英文小写（README.md 例外）；
- 技能条目数量是否达标（提示词 ≥8、案例模板 ≥6、踩坑 ≥18）；
- `evidence.md` 里反引号引用的包内路径是否真实存在。

```bash
python skill/validation/check_skill.py
# 退出码 0 = 全部通过；1 = 有失败项（会打印失败清单）
```

**已验证效果**：本包运行约 1 秒，覆盖 60+ 项检查。

**复用方式**：换题目时保留本脚本、替换 `REQUIRED_FILES` 与条目数量阈值即可。

## 2. `check_package.py` —— 工程包自检（本工程用）

检查：
- 目录结构是否符合约定（src/sim/build/board/data/skill/report）；
- 关键产物是否存在（源码、位流、BOOT.bin、报告、日志）；
- 源码关键标记（`ap_fixed<16,7>`、`SCALE=512`、FatFS `f_open`、`ALL DONE` 结束标记）；
- 数据完整性（图片/GT 数量）；
- 日志完整性（帧数、36/36、结束标记）；
- 指标是否在预期区间（GT 命中率、单帧耗时）。

```bash
python skill/validation/check_package.py [package_root]
# 退出码 0 = 全部通过；1 = 有失败项
```

**已验证效果**：本提交包跑一次约 1 秒，56 项检查全部通过。

**失效条件**：如果题目没有 GT 或没有串口日志，第 4/5/6 项需按实际情况裁剪。

## 3. 与本包其他脚本的关系

| 需求 | 脚本 |
|---|---|
| 权重是否就是训练权重的折叠结果 | `../../sim/scripts/legacy/check_weight_identity.py` |
| 量化误差有多大 | `../../sim/scripts/legacy/quantization_sim.py` |
| 板端与 PC 关键点逐点对比 | `../../sim/scripts/legacy/compare_board_vs_pc.py` |
| GT 命中率（板端/PC） | `../../sim/scripts/eval_board_gt.py`、`../../board/scripts/eval_serial_vs_gt.py` |
| 断电重启确定性 | `../../sim/scripts/legacy/determinism_check.py` |
| 串口日志抓取（防残留） | `../../board/scripts/read_serial.ps1` |

## 4. 复用建议（换到别的题目）

1. 先复制 `check_skill.py`（通用）→ 改必备文件清单与条目阈值；
2. 再复制 `check_package.py`（工程相关）→ 改三处：目录白名单、关键产物清单、指标区间；
3. 在 CI/提交前跑一次，失败即阻断；
4. 把自检输出（通过项数、日期）写进设计报告的"复现说明"。

**来源**：本工程曾因"结果文件是旧的"和"权重版本不对"两次误判精度，因此把"批次/哈希/帧数校验"固化成脚本。
