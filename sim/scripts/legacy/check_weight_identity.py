# -*- coding: utf-8 -*-
"""数值比对：SD 卡折叠权重 vs 各 checkpoint 折叠结果（不靠哈希，靠形状+相关性）"""
import glob
import os
import sys

import numpy as np
import torch

ROOT = r'D:\BaiduNetdiskDownload\AI_FOR_YOLOV4'
SD = r'D:\fpga_work\SD_CARD\yolov4_tiny_weights'

# 1) 读 SD 卡权重
p = os.path.join(SD, 'BasicConv1', 'w.bin')
raw = open(p, 'rb').read()
print('SD BasicConv1/w.bin: %d B' % len(raw))
arr = np.frombuffer(raw, dtype='<f4')
print('  按 float32 解析: %d 个值  min=%.4f max=%.4f' % (arr.size, arr.min(), arr.max()))
sdW = arr.reshape(32, 3, 3, 3)
print('  reshape(32,3,3,3) OK')

# 2) 找所有候选 pth
cands = []
for pat in [os.path.join(ROOT, 'work', 'logs_1019', '*.pth'),
            r'D:\YOLOv4-Tiny-超声散斑项目\yolov4-tiny-pytorch\logs\*.pth',
            r'D:\YOLOv4-Tiny-超声散斑项目\yolov4-tiny-pytorch\model_data\*.pth',
            os.path.join(ROOT, 'yolov4-tiny-pytorch-master(1)', 'logs', '*.pth'),
            os.path.join(ROOT, 'yolov4-tiny-pytorch-master(1)', 'model_data', '*.pth')]:
    cands += glob.glob(pat)
cands = sorted(set(cands))
print('\n候选 checkpoint 数:', len(cands))


def fold(st, pre, eps=1e-5):
    W = st[pre + 'conv.weight'].numpy().astype(np.float64)
    b = st[pre + 'conv.bias'].numpy().astype(np.float64) if (pre + 'conv.bias') in st else np.zeros(W.shape[0])
    g = st[pre + 'bn.weight'].numpy(); be = st[pre + 'bn.bias'].numpy()
    mu = st[pre + 'bn.running_mean'].numpy(); va = st[pre + 'bn.running_var'].numpy()
    std = np.sqrt(va + eps)
    Wf = (W * (g / std).reshape(-1, 1, 1, 1)).astype(np.float32)
    bf = ((b - mu) * g / std + be).astype(np.float32)
    return Wf, bf


rows = []
for c in cands:
    try:
        st = torch.load(c, map_location='cpu')
    except Exception:
        continue
    try:
        Wf, bf = fold(st, 'backbone.conv1.')
    except Exception:
        continue
    if Wf.shape == sdW.shape:
        a = sdW.ravel(); b = Wf.ravel()
        corr = float(np.corrcoef(a, b)[0, 1])
        d = float(np.abs(a - b).max())
        rows.append((corr, d, os.path.getsize(c), c))

rows.sort(key=lambda t: -t[0])
print('\n%-8s %-12s %-10s %s' % ('相关性', '最大差', '大小', '文件'))
for corr, d, size, path in rows[:10]:
    print('%-8.5f %-12.4f %-10d %s' % (corr, d, size, path))
