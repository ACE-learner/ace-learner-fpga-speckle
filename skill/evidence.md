# 证据索引（Evidence Index）

> 本文件把技能包/报告里出现的每个数字，落到 **证据文件 + 复现命令 + 口径说明**。
> 规则：**没有证据路径的数字不写进报告**；估算值必须标注"估算/实测"。

## 1. 精度与一致性

| 指标 | 数值 | 证据文件 | 复现命令 | 口径/备注 |
|---|---|---|---|---|
| 板端 GT 命中（A4C 54 帧） | **79.12%（1538/1944）** | `board/logs/log_toshiba_a4c_54f_100mhz.txt` | `python board/scripts/eval_serial_vs_gt.py board/logs/log_toshiba_a4c_54f_100mhz.txt data/images_toshiba_a4c data/labels_toshiba_a4c` | 容差 `max(w,h)/2+4 px`（本项目约 11 px）；命中=预测点落在 GT 容差圆内 |
| PC float 参考 | **77.88%** | `sim/results/summary_metrics.csv` | `python sim/scripts/eval_pc_gt.py --set toshiba`（需 torch） | 同一数据/同一容差 |
| 120 MHz 历史版板端 | 73.87% | `board/logs/log_toshiba_a4c_54f.txt` | 同上（换日志） | 旧解码规则；仅作对比，不作交付指标 |
| 逐类命中率（100 MHz） | 弱类：cls28 39%、cls31 43%、cls29 50%、cls6/16 56% | `data/reference_results/per_class_board_newrule_a4c.csv` | 打开 CSV 或 `sim/results/per_class_board_newrule_a4c.csv` | 说明瓶颈已从部署转向模型本身 |
| 板端 vs PC 关键点一致性 | 96.7% ≤2 px（中位 0.31 px） | `sim/results/` 对比结果 + `sim/README.md` L3 | `python sim/scripts/legacy/compare_board_vs_pc.py`（历史脚本） | 同一帧同一类的逐点距离 |
| 去重位置数（3 px 合并） | A4C 平均 35.2；Philips 平均 33.4（31–36） | `sim/results/board_newrule_a4c_per_frame.csv`；`board/results/` 结果图 header | `python board/scripts/render_from_serial.py <log> data/images_toshiba_a4c <out>`（打印每帧不同位置数） | **不是 36**：36 是类别数；渲染与统计都按去重位置 |

## 2. 性能、时序与功耗

| 指标 | 数值 | 证据文件 | 复现命令/来源 | 口径/备注 |
|---|---|---|---|---|
| 单帧耗时（100 MHz） | **496.6 ms**（496,542–496,596 µs） | `board/logs/log_toshiba_a4c_54f_100mhz.txt` | 搜 `image N time elapsed is` | 固件 ARM 侧计时，含 SD 读取与串口打印开销 |
| 帧率（100 MHz） | 2.01 FPS | 同上 | `1e6 / 平均耗时` | — |
| 单帧耗时（120 MHz 历史） | 421.5 ms / 2.37 FPS | `board/logs/log_toshiba_a4c_54f.txt` | 同上 | 仅对比 |
| 时序（100 MHz 交付版） | WNS **+0.336 ns**、TNS 0、0 失败端点 | `build/reports/timing_summary_routed.rpt` | Vivado `report_timing_summary` | 布线后报告；时钟 10 ns |
| 时序（120 MHz 历史版） | WNS −0.921 ns、TNS −14.393 ns、61 失败端点 | `build/reports/historical_120mhz/timing_summary_routed.rpt` | 同上 | 历史对比；已不交付 |
| 片上功耗（100 MHz） | **2.953 W**（动态 2.753 + 静态 0.200） | `build/reports/power_routed.rpt` | Vivado `report_power` | **Vivado vectorless 估算**，Confidence Medium，非板级实测 |
| 片上功耗（120 MHz 历史） | 3.212 W（2.999 + 0.214） | `build/reports/historical_120mhz/power_routed.rpt` | 同上 | 同上 |
| 资源占用（100 MHz） | LUT 43,980（82.67%）、FF 42,901（40.32%）、BRAM 94.5（67.5%）、DSP 218/220（99.09%） | `build/reports/utilization_routed.rpt` | Vivado `report_utilization` | DSP 接近上限，是提速硬瓶颈 |
| 峰值算力/能效（100 MHz） | 43.6 GOPS；14.77 GOPS/W | 由 `218×2×100 MHz` 与 2.953 W 计算 | 手算 | 理论峰值/估算功耗，需注明口径 |
| 板级功耗 | **未实测** | — | 需 12V 功率计（步骤见 `board/README.md` 第 8 节） | 不得把 2.953 W 写成"实测" |

## 3. 确定性与复现

| 检查 | 结果 | 证据 | 复现命令 |
|---|---|---|---|
| 断电重启确定性（120 MHz 历史） | 两次运行逐位一致（conf 差 0、位置差 0） | `board/logs/log_powercycle_round1.txt`、`board/logs/log_powercycle_round2.txt` | `python sim/scripts/legacy/determinism_check.py` |
| 100 MHz vs 120 MHz 结果一致性 | 1899 条 K 行位置/分数逐位一致 | `board/logs/log_toshiba_a4c_54f_100mhz.txt` 与 `board/logs/log_toshiba_a4c_54f.txt` | 逐行解析两份日志比较（`sim/scripts/legacy/determinism_check.py` 思路） |
| 技能包自检 | 全部通过 | 本目录 | `python skill/validation/check_skill.py` |
| 工程包自检 | 56/56 通过 | `skill/validation/check_package.py` | `python skill/validation/check_package.py` |
| 通用 PYNQ 技能离线自检 | 4 套脚本逻辑 PASS | `skill/pynq/README.md` 离线自检表 | 见 `pynq/README.md` 各命令（mock 模式） |

## 4. 口径与限制（写报告时必须一起给）

1. **容差口径**：GT 是"点标注转固定 12×14 px 框"，容差约 11 px；79% 是"容差内命中率"，**不等于亚像素精度**（≤5 px 仅约 42%，≤2 px 约 10%）。
2. **频率版本**：交付版 100 MHz（496.6 ms/2.01 FPS）；120 MHz 版 421.5 ms 时序未收敛，仅作性能对比。
3. **功耗口径**：Vivado 片上估算 ≠ 板级实测；报告需分列，实测需外部功率计。
4. **确定性范围**：同一份位流 + 同一份输入 + 同一固件下的重复运行；换频率/改代码后需重新验证。
5. **可迁移性**：技能方法可迁移；本工程数值（79.12%、496.6 ms 等）只作为"该方法已跑通"的证据，不是对新题目的承诺。
