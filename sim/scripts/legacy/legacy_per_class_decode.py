# -*- coding: utf-8 -*-
"""对比两种解码方式（板端 54 帧）：
   A. 原方式：每个框做 36 类 argmax -> 每类保留最高分（类别会因竞争丢失）
   B. 新方式：每个类在自己所有位置上独立取最高分（不参与 argmax 竞争）
"""
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


def raw_boxes(o0, o1):
    """返回所有候选框 [N, 4+1+36]：(cx, cy, w, h, obj, 36 类分数)"""
    with torch.no_grad():
        outs = bu.decode_box([o0, o1])
        return torch.cat(outs, 1)[0]


def argmax_compete(out, conf=0.005):
    """原方式：每个框 argmax 类别，再每类保留最高分"""
    obj = out[:, 4]
    cls = out[:, 5:5 + NC]
    s, idx = cls.max(dim=1)
    sc = obj * s
    m = sc >= conf
    res = {}
    for c, scv in zip(idx[m], sc[m]):
        c = int(c)
        scv = float(scv)
        if c not in res or scv > res[c]:
            res[c] = scv
    return res


def per_class_top1(out, conf=0.001):
    """新方式：每个类独立取全场最高分（类之间不竞争）"""
    obj = out[:, 4]
    cls = out[:, 5:5 + NC]
    score = obj.unsqueeze(1) * cls          # [N, 36]
    best_score, _ = score.max(dim=0)
    res = {}
    for c in range(NC):
        s = float(best_score[c])
        if s >= conf:
            res[c] = s
    return res


rows = []
for i in range(54):
    b0 = torch.from_numpy(np.fromfile(os.path.join(GD, f'out0_{i}.bin'), dtype='<f4').copy().reshape(1, 123, 13, 13))
    b1 = torch.from_numpy(np.fromfile(os.path.join(GD, f'out1_{i}.bin'), dtype='<f4').copy().reshape(1, 123, 26, 26))
    out = raw_boxes(b0, b1)
    rows.append((len(argmax_compete(out)), len(per_class_top1(out))))

rows = np.array(rows)
print('=== FPGA 板端 54 帧：类别覆盖数 ===')
print('A 原方式(argmax竞争): 最小 %d, 最大 %d, 平均 %.1f' % (rows[:, 0].min(), rows[:, 0].max(), rows[:, 0].mean()))
print('B 每类独立top1     : 最小 %d, 最大 %d, 平均 %.1f' % (rows[:, 1].min(), rows[:, 1].max(), rows[:, 1].mean()))

# PC 端对照
net = YoloBody(MASK, NC, phi=0, pretrained=False)
net.load_state_dict(torch.load(os.path.join(ROOT, 'work', 'logs_1019', 'best_epoch_weights.pth'), map_location='cpu'), strict=True)
net.eval()
cnt_pc = []
for i in range(54):
    inp = torch.from_numpy(np.fromfile(os.path.join(GD, f'img{i}.bin'), dtype='<f4').copy().reshape(1, 3, 416, 416))
    with torch.no_grad():
        p0, p1 = net(inp)
    cnt_pc.append(len(per_class_top1(raw_boxes(p0.cpu(), p1.cpu()))))
cnt_pc = np.array(cnt_pc)
print('')
print('PC 端(每类独立top1): 最小 %d, 最大 %d, 平均 %.1f' % (cnt_pc.min(), cnt_pc.max(), cnt_pc.mean()))
