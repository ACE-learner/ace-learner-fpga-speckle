# -*- coding: utf-8 -*-
"""逐类对照：板端 vs PC 的 per-class top1 分数/位置，找塌缩规律"""
import os
import sys

import numpy as np
import torch
from PIL import Image

ROOT = r'D:\BaiduNetdiskDownload\AI_FOR_YOLOV4'
PROJ = os.path.join(ROOT, 'yolov4-tiny-pytorch-master(1)')
GD = r'D:\fpga_work\board_out'
NC, MASK = 36, [[3, 4, 5], [1, 2, 3]]

sys.path.insert(0, PROJ)
from nets.yolo import YoloBody
from utils.utils import get_anchors
from utils.utils_bbox import DecodeBox

anchors, _ = get_anchors(os.path.join(PROJ, 'model_data', 'yolo_anchors.txt'))
bu = DecodeBox(anchors, NC, (416, 416), MASK)
net = YoloBody(MASK, NC, phi=0, pretrained=False)
net.load_state_dict(torch.load(os.path.join(ROOT, 'work', 'logs_1019', 'best_epoch_weights.pth'), map_location='cpu'), strict=True)
net.eval()


def kp(pred, iw, ih):
    obj = pred[:, 4]
    cls = pred[:, 5:5 + NC]
    score = (obj.unsqueeze(1) * cls).numpy()
    cxy = pred[:, :2].numpy()
    out = {}
    for c in range(NC):
        i = int(score[:, c].argmax())
        out[c] = (cxy[i, 0] * iw, cxy[i, 1] * ih, float(score[i, c]))
    return out


frame = 2
im = Image.open(os.path.join(GD, f'img{frame}.png'))
iw, ih = im.size

b0 = torch.from_numpy(np.fromfile(os.path.join(GD, f'out0_{frame}.bin'), dtype='<f4').copy().reshape(1, 123, 13, 13))
b1 = torch.from_numpy(np.fromfile(os.path.join(GD, f'out1_{frame}.bin'), dtype='<f4').copy().reshape(1, 123, 26, 26))
with torch.no_grad():
    outs = bu.decode_box([b0, b1])
    pb = torch.cat(outs, 1)[0]
kb = kp(pb, iw, ih)

inp = torch.from_numpy(np.fromfile(os.path.join(GD, f'img{frame}.bin'), dtype='<f4').copy().reshape(1, 3, 416, 416))
with torch.no_grad():
    p0, p1 = net(inp)
    outs = bu.decode_box([p0, p1])
    pp = torch.cat(outs, 1)[0]
kp_ = kp(pp, iw, ih)

print('帧 %d：逐类对照（板端 vs PC）' % frame)
print('%4s %8s %8s %8s %10s' % ('类', '板端分', 'PC分', '分差', '位置差px'))
diffs = []
for c in range(NC):
    xb, yb, sb = kb[c]
    xp, yp, sp = kp_[c]
    d = float(np.hypot(xb - xp, yb - yp))
    diffs.append((abs(sb - sp), c, sb, sp, d))
for _, c, sb, sp, d in sorted(diffs, reverse=True):
    print('%4d %8.3f %8.3f %8.3f %10.2f' % (c, sb, sp, sb - sp, d))

print()
print('板端分数均值 %.3f   PC 分数均值 %.3f' % (np.mean([v[2] for v in kb.values()]), np.mean([v[2] for v in kp_.values()])))
print('位置差：平均 %.2f px，最大 %.2f px' % (np.mean([d[4] for d in diffs]), max(d[4] for d in diffs)))
print('位置差 >5px 的类数: %d' % sum(1 for d in diffs if d[4] > 5))
