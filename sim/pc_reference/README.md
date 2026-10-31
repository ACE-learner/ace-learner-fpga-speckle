# PC 端参考实现（PyTorch）

本目录是从训练工程中复制出来的**最小推理代码**，用于让 `sim/scripts/` 的评测脚本可以在没有完整训练工程（数 GB）的机器上运行。

## 内容来源

| 路径 | 来源 | 说明 |
|---|---|---|
| `nets/` | yolov4-tiny-pytorch 训练工程 | 模型结构（`YoloBody`、CSPdarknet53_tiny 等） |
| `utils/` | 同上 | `get_anchors`、`DecodeBox`、NMS 等 |
| `model_data/yolo_anchors.txt` | 同上 | 6 个先验框尺寸 |
| `model_data/classes.txt` | 同上 | 类别名（36 类） |

## 运行依赖

- Python 3.8+（本包在 3.13.16 上验证）
- `torch`（CPU 即可；本包在 torch 2.15.0.dev 上验证）
- `numpy`
- 权重：`data/weights/logs_1019_best_epoch_weights.pth`（23,889,255 B）

## 用法

```bash
python sim/scripts/eval_pc_gt.py --set philips
python sim/scripts/eval_pc_gt.py --set toshiba
```

预期结果（与 `sim/results/summary_metrics.csv` 一致）：

| 数据 | GT 命中率 |
|---|---|
| Philips A3C（50 帧）| 68.72% |
| TOSHIBA A4C（54 帧）| 77.88% |

## 说明

- 本目录代码版权归原训练工程作者；仅用于本作品的复现与评测。
- 输入预处理必须与板端一致：RGB → BICUBIC 缩放到 416×416 → 除以 255 → CHW。
- 不要用其他 checkpoint 替换权重：项目里有多份权重，只有 `logs_1019`（Oct-20）能复现上述结果。
