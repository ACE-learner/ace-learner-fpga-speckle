# -*- coding: utf-8 -*-
"""核对：SD 卡上的折叠权重到底来自哪个 checkpoint
方法：把每个候选 .pth 按同样规则折叠 BN，比较 BasicConv1/ResBlock1 的几个 w.bin 是否字节一致
"""
import hashlib
import os
import sys

import numpy as np
import torch

ROOT = r'D:\BaiduNetdiskDownload\AI_FOR_YOLOV4'
sys.path.insert(0, os.path.join(ROOT, '毕设', '毕设', 'predictor'))

CANDIDATES = [
    ('PC对比用(logs_1019 Oct20)', os.path.join(ROOT, 'work', 'logs_1019', 'best_epoch_weights.pth')),
    ('项目logs(10-19 18:37)', r'D:\YOLOv4-Tiny-超声散斑项目\yolov4-tiny-pytorch\logs\best_epoch_weights.pth'),
    ('项目model_data', r'D:\YOLOv4-Tiny-超声散斑项目\yolov4-tiny-pytorch\model_data\best_epoch_weights.pth'),
    ('毕设logs(05-03)', r'D:\BaiduNetdiskDownload\AI_FOR_YOLOV4\毕设\毕设\yolov4_tiny\yolov4_tiny\logs\best_epoch_weights.pth'),
    ('仓库logs(05-03)', r'D:\BaiduNetdiskDownload\AI_FOR_YOLOV4\yolov4-tiny-pytorch-master(1)\logs\best_epoch_weights.pth'),
]

# SD 卡上的折叠权重目录（找一份即可）
SD_DIRS = [
    r'D:\fpga_work\SD_CARD\yolov4_tiny_weights',
    r'D:\fpga_work\sd_weights_oct20',
    r'E:\yolov4_tiny_weights',
]
sd = next((d for d in SD_DIRS if os.path.isdir(d)), None)
print('SD 折叠权重目录:', sd)
if sd:
    for sub in ('BasicConv1', 'ResBlock1'):
        for f in ('w.bin',):
            p = os.path.join(sd, sub, f)
            if os.path.exists(p):
                print('  %-40s %d B  sha256=%s' % (os.path.join(sub, f), os.path.getsize(p),
                      hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]))


def fold(state, pre, eps=1e-5):
    W = state[pre + 'conv.weight'].numpy().astype(np.float64)
    b = state[pre + 'conv.bias'].numpy().astype(np.float64) if (pre + 'conv.bias') in state else np.zeros(W.shape[0])
    g = state[pre + 'bn.weight'].numpy(); be = state[pre + 'bn.bias'].numpy()
    mu = state[pre + 'bn.running_mean'].numpy(); va = state[pre + 'bn.running_var'].numpy()
    std = np.sqrt(va + eps)
    return (W * (g / std).reshape(-1, 1, 1, 1)).astype(np.float32), ((b - mu) * g / std + be).astype(np.float32)


print('\n各 checkpoint 的折叠权重指纹（BasicConv1 w.bin 前 4 个浮点 + sha256 前16）:')
target = None
if sd:
    p = os.path.join(sd, 'BasicConv1', 'w.bin')
    if os.path.exists(p):
        target = hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]

for name, path in CANDIDATES:
    if not os.path.exists(path):
        print('  %-28s (不存在)' % name)
        continue
    try:
        st = torch.load(path, map_location='cpu')
        Wf, bf = fold(st, 'backbone.conv1.')
        raw = Wf.astype('<f4').tobytes()
        h = hashlib.sha256(raw).hexdigest()[:16]
        flag = ' <== 与 SD 卡一致' if (target and h == target) else ''
        print('  %-28s sha=%s%s' % (name, h, flag))
    except Exception as e:
        print('  %-28s 失败: %s' % (name, e))
