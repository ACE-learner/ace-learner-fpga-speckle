# -*- coding: utf-8 -*-
"""对比多次板端运行的 ARM 关键点统计（判断是否不稳定 = 时序违例）"""
import re
import sys

import numpy as np

FILES = [
    ('run1 (20:36)', r'D:\BaiduNetdiskDownload\AI_FOR_YOLOV4\work\fpga\serial_armkp.txt'),
    ('run2 (20:4x)', r'D:\BaiduNetdiskDownload\AI_FOR_YOLOV4\work\fpga\serial_armkp_run2.txt'),
]

all_frames = {}
for name, path in FILES:
    txt = open(path, encoding='utf-8', errors='ignore').read()
    frames = {}
    for m in re.finditer(r'K (\d+) (\d+) ([\-\d\.]+) ([\-\d\.]+) ([\-\d\.]+)', txt):
        f = int(m.group(1)); c = int(m.group(2))
        frames.setdefault(f, {})[c] = (float(m.group(3)), float(m.group(4)), float(m.group(5)))
    kpt = [int(m.group(2)) for m in re.finditer(r'KPT (\d+) (\d+)', txt)]
    ns = [len(frames[f]) for f in sorted(frames)]
    cs = [np.mean([v[2] for v in frames[f].values()]) for f in sorted(frames)]
    print('%-14s 帧数=%2d  关键点平均 %.1f（min %d/max %d）  conf 平均 %.3f  KPT耗时 %.0f us'
          % (name, len(frames), np.mean(ns) if ns else 0, min(ns) if ns else 0, max(ns) if ns else 0,
             np.mean(cs) if cs else 0, np.mean(kpt) if kpt else 0))
    all_frames[name] = frames

# 逐帧对比两轮
if len(all_frames) == 2:
    n1, n2 = list(all_frames.keys())
    f1, f2 = all_frames[n1], all_frames[n2]
    common_f = sorted(set(f1) & set(f2))
    print()
    print('=== 两轮逐帧对比（共 %d 帧）===' % len(common_f))
    print('%4s %10s %10s %10s %10s' % ('帧', 'run1 conf', 'run2 conf', 'conf差', '位置差px'))
    diffs = []
    for f in common_f[:12]:
        c1 = np.mean([v[2] for v in f1[f].values()])
        c2 = np.mean([v[2] for v in f2[f].values()])
        d = []
        for c in set(f1[f]) & set(f2[f]):
            d.append(np.hypot(f1[f][c][0] - f2[f][c][0], f1[f][c][1] - f2[f][c][1]))
        md = np.mean(d) if d else float('nan')
        diffs.append((c1, c2, md))
        print('%4d %10.3f %10.3f %10.3f %10.1f' % (f, c1, c2, c1 - c2, md))
    dd = np.array(diffs)
    print()
    print('两轮 conf 差: 平均 %.3f（最大 %.3f）' % (np.abs(dd[:, 0] - dd[:, 1]).mean(), np.abs(dd[:, 0] - dd[:, 1]).max()))
    print('两轮位置差: 平均 %.1f px' % np.nanmean(dd[:, 2]))
    if np.abs(dd[:, 0] - dd[:, 1]).mean() > 0.01 or np.nanmean(dd[:, 2]) > 1.0:
        print('=> 两轮结果不一致，板端计算存在不确定性（时序违例嫌疑）')
    else:
        print('=> 两轮结果一致，计算是确定性的')
