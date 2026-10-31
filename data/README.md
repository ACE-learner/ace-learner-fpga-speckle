# 测试数据（Data）

本目录提供两组带人工标注（GT）的超声序列，用于复现精度评测。

## 1. 数据结构

```
data/
├─ images_philips_a3c/     # Philips A3C/rca 序列：img0.png ... img49.png（642x488，50 帧）
│                          # 另含 img0~img5.bin（416x416 float32 编码示例）与 img_num.txt
├─ labels_philips_a3c/     # 对应 GT：0001.txt ... 0050.txt
├─ images_toshiba_a4c/     # TOSHIBA A4C/normal 序列：img0.png ... img53.png（636x489，54 帧）
├─ labels_toshiba_a4c/     # 对应 GT：g0.txt ... g53.txt
└─ reference_results/      # 参考结果（CSV）
```

## 2. GT 标注格式

每个 txt 文件包含 36 行，每行：
```
<class_id> <cx> <cy> <w> <h>
```
- 全部为**归一化到 0~1** 的 YOLO 格式（cx,cy 为中心，w,h 为宽高）
- class_id = 0~35，对应心内膜环上按角度顺序排列的 36 个关键点

## 3. 输入编码格式（板端使用）

`imgN.bin`：
- 尺寸 `416 × 416 × 3`，float32
- 布局 **CHW**（channel-first）
- 预处理：RGB → BICUBIC 缩放到 416×416 → 除以 255

编码脚本：`../board/scripts/encode_images.py`

## 4. 参考结果（`reference_results/`）

| 文件 | 内容 |
|---|---|
| `summary_metrics.csv` | 两组数据的板端/PC GT 命中率、置信度、单帧耗时（含新规则行 `*_newrule`；旧行标记 legacy） |
| `board_newrule_a4c_per_frame.csv` | 新规则 A4C 54 帧逐帧统计 |
| `per_class_board_newrule_a4c.csv` | 新规则逐类命中率 |
| `board_philips_a3c_per_frame.csv` | Philips 50 帧逐帧统计（检测位置数/命中数/conf） |
| `board_toshiba_a4c_per_frame.csv` | TOSHIBA 54 帧逐帧统计 |
| `determinism_powercycle.csv` | 两次断电重启逐帧对比（差值全为 0） |
| `per_class_board_vs_pc_toshiba.csv` | TOSHIBA 逐类命中率（板端 vs PC） |

## 5. 评测口径

- 命中判定：预测点与 GT 中心的距离 ≤ `max(w_px, h_px)/2 + 4 px`
- 板端输出为归一化坐标，乘以图片真实尺寸后与 GT 比较
- PC 端参考：PyTorch 前向 + `conf=0.05, nms=0.3` 解码（每类保留最高分框）

## 6. 数据来源与使用限制

数据来源于公开超声心动图数据集（原始 6165 张，含 7 个厂商、多个切面与节段）。本目录仅保留两组评测序列（共 104 帧）用于复现，
原始完整数据与训练集划分不在本包内（避免体积过大）。版权归原始数据提供方所有，仅用于本竞赛的算法验证。
