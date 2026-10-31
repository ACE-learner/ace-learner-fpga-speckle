# -*- coding: utf-8 -*-
"""复现 测试结果.zip 的生成口径，确定它用的权重与计数方式
参考图 img2.png 的标注是: keypoints 36/36, raw boxes 43, mean conf 0.49
解码方式对应 predict_usb.py: NMS(conf=0.05, nms=0.3) -> 每类保留最高分
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

CANDS = {
    'model_data/best_epoch_weights.pth (23888836)': os.path.join(PROJ, 'model_data', 'best_epoch_weights.pth'),
    'logs_1019 (Oct20, 23889255)': os.path.join(ROOT, 'work', 'logs_1019', 'best_epoch_weights.pth'),
    '项目 logs/best (10-19, 23889255)': r'D:\YOLOv4-Tiny-超声散斑项目\yolov4-tiny-pytorch\logs\best_epoch_weights.pth',
}

frame = 2
im = Image.open(os.path.join(GD, f'img{frame}.png'))
iw, ih = im.size
inp = torch.from_numpy(np.fromfile(os.path.join(GD, f'img{frame}.bin'), dtype='<f4').copy().reshape(1, 3, 416, 416))

print('参考: img2.png -> keypoints 36/36, raw boxes 43, mean conf 0.49  (conf=0.05, nms=0.3)')
print()
for name, path in CANDS.items():
    if not os.path.exists(path):
        print('%-42s 不存在' % name)
        continue
    net = YoloBody(MASK, NC, phi=0, pretrained=False)
    net.load_state_dict(torch.load(path, map_location='cpu'), strict=True)
    net.eval()
    with torch.no_grad():
        p0, p1 = net(inp)
        outs = bu.decode_box([p0, p1])
        res = bu.non_max_suppression(torch.cat(outs, 1), NC, (416, 416),
                                     np.array([ih, iw]), False, conf_thres=0.05, nms_thres=0.3)
    if res[0] is None:
        print('%-42s 无检测' % name)
        continue
    a = res[0]
    raw = len(a)
    cls = a[:, 6].astype(int)
    score = a[:, 4] * a[:, 5]
    best = {}
    for c, s in zip(cls, score):
        if c not in best or s > best[c]:
            best[c] = float(s)
    mean_conf = float(np.mean(list(best.values())))
    print('%-42s raw=%2d  keypoints=%2d/36  mean conf=%.3f' % (name, raw, len(best), mean_conf))
