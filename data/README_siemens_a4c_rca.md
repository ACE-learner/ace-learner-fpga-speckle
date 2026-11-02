# data/README_siemens_a4c_rca.md

## Siemens A4C / rca（56 帧）测试集

本目录是项目实际使用的 Siemens A4C / rca 序列，从百度网盘数据集中的
`数据集/Siemens/A4C/rca/` 导入，已按本工程命名规范整理：

```
data/
├─ images_siemens_a4c_rca/
│  ├─ img0.png … img55.png     # 原图（736×617，56 帧）
│  └─ img_num.txt              # 56
└─ labels_siemens_a4c_rca/
   └─ g0.txt … g55.txt         # GT：cls cx cy w h（归一化）
```

命名映射：

| 原始文件 | 本工程文件 |
|---|---|
| `png/0001.png … 0056.png` | `img0.png … img55.png` |
| `labels/0001.txt … 0056.txt` | `g0.txt … g55.txt` |

用途：

- 编码/写卡：`board/scripts/prepare_images.bat` 选择本目录的 `images_siemens_a4c_rca`；
- 结果渲染：`board/scripts/render_results.bat -ImageDir data/images_siemens_a4c_rca`；
- GT 评测：`board/scripts/eval_serial_vs_gt.py <串口日志> data/images_siemens_a4c_rca data/labels_siemens_a4c_rca`。

板端 100 MHz 实测（56 帧）：

- 每帧不同位置数：平均 35.1（min 34 / max 36）
- GT 命中：1562 / 2016 = **77.48%**（容差 `max(w,h)/2 + 4 px`）
- 平均置信度：0.514

## 关于完整数据集

百度网盘中的完整数据集约 **0.75 GB（12,491 个文件）**，包含 7 个厂商的
A2C/A3C/A4C × 5 个切面序列与对应 labels，不适合直接放进普通 Git 仓库。
本仓库内置的是**复现报告与板端测试实际用到的子集**：

| 数据集 | 本仓库位置 | 帧数 |
|---|---|---|
| Siemens A4C / rca | `data/images_siemens_a4c_rca` + `data/labels_siemens_a4c_rca` | 56 |
| TOSHIBA A4C | `data/images_toshiba_a4c` + `data/labels_toshiba_a4c` | 54 |
| Philips A3C | `data/images_philips_a3c` + `data/labels_philips_a3c` | 50 |

完整数据集已发布为 GitHub Release：

- 页面：https://github.com/ACE-learner/ace-learner-fpga-speckle/releases/tag/dataset-v1.0
- 压缩包：`ultrasound_speckle_dataset_full_2026-11.zip`（759.9 MB，SHA256 `63ef79a...c1aff`）

不要直接提交进普通 Git 历史。

## 版权与使用

数据来源于项目使用的公开超声心动图数据集，版权归原数据集发布方所有；
本仓库仅保留复现所需的测试子集，不含患者身份信息。仅用于本竞赛复现与学术研究，
不得用于临床诊断或商业用途；如涉及版权/隐私问题，请联系维护者删除。
