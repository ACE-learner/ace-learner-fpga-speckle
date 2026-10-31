# 通用 PYNQ 技能包（可迁移到任意 PYNQ 题目/板卡）

> 本目录与"超声散斑/36 关键点"题目无关，示例均为通用矩阵/图像计算 IP。
> 目标：一支陌生队伍拿到本目录，可以在自己的 PYNQ 板卡上直接复用这四套流程。
> 每项都写明：适用范围、使用方法、已验证效果、失效条件。

## 技能索引

| 编号 | 技能 | 一句话用途 | 适用范围 | 验证状态 | 失效条件 |
|---|---|---|---|---|---|
| 01 | Overlay 导出与加载 | Vivado 位流 + .hwh 在 PYNQ 里成功加载并能读写寄存器 | 任意"自定义 IP + PYNQ"题目 | 离线自检通过（脚本逻辑/`.hwh` 解析/回读流程）；上板验证由使用者执行 `check_overlay.py` | `.hwh` 缺失、器件型号/PS 配置不匹配 |
| 02 | AXI-DMA 数据通路 | 打通 PS 内存 ↔ PL 的 DMA 传输并验证数据一致性、测吞吐 | 需要批量数据搬运的加速器（图像/矩阵） | 离线自检通过（图案生成/校验/吞吐计算）；上板验证执行 `validate_dma.py` | 无 DMA IP、中断未接、缓存一致性未处理 |
| 03 | 环境与离线部署 | 板端 PYNQ 环境自查、无网络时离线装依赖、Jupyter 配置 | 任何 PYNQ 板卡 | 脚本逻辑与输出格式离线验证；板端运行 `check_env.py` | 官方镜像未适配该板、镜像版本不匹配 |
| 04 | 性能测量与可信度 | 正确测延迟/吞吐（预热、分位数、CSV），排查"结果不可信" | 任何需要报告板端性能的题目 | 脚本可离线跑通（含 mock 模式） | 测量代码把编译/首次加载算进稳态 |

## 使用方法（推荐顺序）

1. 拿到 PYNQ 板后先跑 `03_env_and_offline_deploy/check_env.py`：确认 pynq 版本、板卡、内存、overlay 目录可用。
2. 按 `01_overlay_bringup/README.md` 导出 .bit/.hwh 并跑 `check_overlay.py`：确认 overlay 能加载、IP 列表与 Vivado 一致。
3. 按 `02_axi_dma_datapath/README.md` 跑 `dma_loopback.py` / `validate_dma.py`：确认数据通路正确、吞吐达标。
4. 用 `04_bench_and_trust/bench_template.py` 产出可写进报告的延迟/吞吐数据（CSV）。
5. 把每步的输出（版本号、IP 列表、吞吐、分位数）填进 README 的"实机验证记录"一节，即为可复现的验证证据。

## 离线自检结果（本包已执行，PC 环境 Python 3.13.16 + numpy 2.5.2）

| 技能 | 命令 | 结果 |
|---|---|---|
| 01 Overlay | `python 01_overlay_bringup/check_overlay.py --mock` | 4 项检查全部 PASS |
| 02 DMA | `python 02_axi_dma_datapath/validate_dma.py --mock --repeat 20` | 一致性/统计/CSV 逻辑 PASS |
| 03 环境 | `python 03_env_and_offline_deploy/check_env.py` | 14 项检查，0 FAIL（PC 上 8 WARN 属预期） |
| 04 性能 | `python 04_bench_and_trust/bench_template.py --mock --repeat 11` | 预热/分位数/CSV 逻辑 PASS |
| 语法 | `python -m py_compile *.py` | 6 个脚本全部通过 |

说明：以上验证的是脚本逻辑（解析、校验、统计、CSV），不包含 PYNQ API 的真实调用效果（本队无 PYNQ 实机）。

## 实机验证记录（使用者填写）

| 技能 | 板卡/镜像 | 命令 | 输出摘要 | 日期 |
|---|---|---|---|---|
| 01 | 例：PYNQ-Z2 / PYNQ 2.7 | check_overlay.py --bit ... | PASS, N IPs | |
| 02 | | validate_dma.py --bit ... | 100/100 一致, xx MB/s | |
| 03 | | check_env.py | 0 FAIL | |
| 04 | | bench_template.py --ip ... | p50=xx ms | |

## 目录结构

```
pynq/
├── README.md                       # 本文件
├── 01_overlay_bringup/
│   ├── README.md
│   ├── overlay_bringup.py          # 加载 overlay + 列 IP + 寄存器读写模板
│   └── check_overlay.py            # 自检：文件/JSON/加载/IP 一致性（含 mock 模式）
├── 02_axi_dma_datapath/
│   ├── README.md
│   ├── dma_loopback.py             # DMA 图案回环模板 + 吞吐计算
│   └── validate_dma.py             # 自检：多次传输一致性 + 吞吐 CSV
├── 03_env_and_offline_deploy/
│   ├── README.md
│   └── check_env.py                # 板端环境自检（可在 PC 上部分运行）
└── 04_bench_and_trust/
    ├── README.md
    └── bench_template.py           # 延迟/吞吐测量模板（预热 + 分位数 + CSV）
```

## 版本兼容说明

| 项目 | 说明 |
|---|---|
| PYNQ 版本 | 2.5 / 2.6 / 2.7 / 3.x 之间 API 有差异：`Buffer.sync_to_device()/sync_from_device()` 为 2.6+，旧版用 `flush()/invalidate()`；脚本里已做兼容分支 |
| 板卡 | PYNQ-Z1/Z2（Zynq-7020）、ZCU104（UltraScale+）、Kria 等；镜像必须与板卡匹配 |
| Vivado | 2019.1+ 导出的 `.hwh` 为 JSON 格式；更老的版本是 XML，`check_overlay.py` 对两者都做检测 |
