# -*- coding: utf-8 -*-
"""ARM 端关键点 vs PC PyTorch（同一批输入 img{i}.bin + 同一权重）逐类对比"""
import os
import re
import sys

import numpy as np
import torch
from PIL import Image

ROOT = r'D:\BaiduNetdiskDownload\AI_FOR_YOLOV4'
PROJ = os.path.join(ROOT, 'yolov4-tiny-pytorch-master(1)')
GD = r'D:\fpga_work\board_out'
NC, MASK = 36, [[3, 4, 5], [1, 2, 3]]
LOG = r'D:\BaiduNetdiskDownload\AI_FOR_YOLOV4\work\fpga\serial_armkp.txt'

txt = open(LOG, encoding='utf-8', errors='ignore').read()
arm = {}
for m in re.finditer(r'K (\d+) (\d+) ([\-\d\.]+) ([\-\d\.]+) ([\-\d\.]+)', txt):
    f = int(m.group(1)); c = int(m.group(2))
    arm.setdefault(f, {})[c] = (float(m.group(3)), float(m.group(4)), float(m.group(5)))

sys.path.insert(0, PROJ)
from nets.yolo import YoloBody
from utils.utils import get_anchors
from utils.utils_bbox import DecodeBox

anchors, _ = get_anchors(os.path.join(PROJ, 'model_data', 'yolo_anchors.txt'))
bu = DecodeBox(anchors, NC, (416, 416), MASK)
net = YoloBody(MASK, NC, phi=0, pretrained=False)
net.load_state_dict(torch.load(os.path.join(ROOT, 'work', 'logs_1019', 'best_epoch_weights.pth'), map_location='cpu'), strict=True)
net.eval()


def pc_keypoints(i):
    """PC 端：每类独立 top1（与 ARM 算法一致）+ 归一化坐标 -> 像素"""
    im = Image.open(os.path.join(GD, f'img{i}.png'))
    iw, ih = im.size
    inp = torch.from_numpy(np.fromfile(os.path.join(GD, f'img{i}.bin'), dtype='<f4').copy().reshape(1, 3, 416, 416))
    with torch.no_grad():
        p0, p1 = net(inp)
        outs = bu.decode_box([p0, p1])
        pred = torch.cat(outs, 1)[0]
    obj = pred[:, 4]
    cls = pred[:, 5:5 + NC]
    score = (obj.unsqueeze(1) * cls).numpy()
    cxy = pred[:, :2].numpy()
    out = {}
    for c in range(NC):
        k = int(score[:, c].argmax())
        out[c] = (float(cxy[k, 0] * iw), float(cxy[k, 1] * ih), float(score[k, c]))
    return out


print('%4s %8s %8s %10s %10s' % ('帧', 'ARMconf', 'PCconf', '位置差均值', '位置差最大'))
all_d, all_dc = [], []
for i in range(min(10, len(arm))):
    a = arm[i]; p = pc_keypoints(i)
    ds = [np.hypot(a[c][0] - p[c][0], a[c][1] - p[c][1]) for c in range(NC) if c in a and c in p]
    dc = [abs(a[c][2] - p[c][2]) for c in range(NC) if c in a and c in p]
    all_d += ds; all_dc += dc
    print('%4d %8.3f %8.3f %10.2f %10.2f'
          % (i, np.mean([v[2] for v in a.values()]), np.mean([v[2] for v in p.values()]),
             np.mean(ds), np.max(ds)))

print()
print('=== 10 帧合计 ===')
print('位置差: 平均 %.2f px，中位 %.2f px，最大 %.2f px'
      % (np.mean(all_d), np.median(all_d), np.max(all_d)))
print('位置差 <=2px 的比例: %.1f%%' % (100 * np.mean(np.array(all_d) <= 2)))
print('位置差 <=5px 的比例: %.1f%%' % (100 * np.mean(np.array(all_d) <= 5)))
print('分数差: 平均 %.3f' % np.mean(all_dc))
