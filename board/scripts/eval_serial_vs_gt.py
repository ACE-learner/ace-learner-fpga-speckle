# -*- coding: utf-8 -*-
"""串口日志（板端 ARM K 行）vs GT 标注评测

用法:
  python eval_serial_vs_gt.py <串口日志.txt> <图片目录> <标签目录>
默认参数（包内路径）:
  log   = 06_文档与结果/串口日志/*.txt（取最新）
  imgs  = 05_测试数据/new_set_A4C
  labels= 05_测试数据/new_set_A4C/labels

判定: 同类别预测点与 GT 点像素距离 <= max(w*W, h*H)/2 + 4 视为命中
"""
import glob
import os
import re
import sys

import numpy as np
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
NC = 36
KP_IMG_W, KP_IMG_H = 670.0, 573.0   # 板端固件归一化参考尺寸（旧格式才需要）


def load_gt(path):
    gt = {}
    if os.path.exists(path):
        for line in open(path):
            v = line.split()
            if len(v) >= 5:
                gt[int(float(v[0]))] = tuple(map(float, v[1:5]))
    return gt


def main():
    if len(sys.argv) >= 2:
        log = sys.argv[1]
        imgs = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, '05_测试数据', 'new_set_A4C')
        labels = sys.argv[3] if len(sys.argv) > 3 else os.path.join(imgs, 'labels')
    else:
        logs = sorted(glob.glob(os.path.join(ROOT, 'board', 'logs', '*.txt')))
        if not logs:
            raise SystemExit('未找到串口日志，请传入日志路径')
        log = logs[-1]
        imgs = os.path.join(ROOT, 'data', 'images_toshiba_a4c')
        labels = os.path.join(ROOT, 'data', 'labels_toshiba_a4c')

    txt = open(log, encoding='utf-8', errors='ignore').read()
    raw = {}
    for m in re.finditer(r'K (\d+) (\d+) ([\d\.\-]+) ([\d\.\-]+) ([\d\.\-]+)', txt):
        f, c = int(m.group(1)), int(m.group(2))
        raw.setdefault(f, {})[c] = (float(m.group(3)), float(m.group(4)), float(m.group(5)))
    if not raw:
        raise SystemExit('日志中没有 K 行: %s' % log)

    hit = tot = 0
    frames = 0
    per_class_hit = {}
    per_class_cnt = {}
    for f in sorted(raw):
        img_path = os.path.join(imgs, 'img%d.png' % f)
        if not os.path.exists(img_path):
            continue
        iw, ih = Image.open(img_path).size
        gt = load_gt(os.path.join(labels, 'g%d.txt' % f))
        if not gt:
            continue
        frames += 1
        for c, (cx, cy, bw, bh) in gt.items():
            gx, gy = cx * iw, cy * ih
            tol = max(bw * iw, bh * ih) / 2.0 + 4.0
            tot += 1
            per_class_cnt[c] = per_class_cnt.get(c, 0) + 1
            if c in raw[f]:
                nx, ny, _ = raw[f][c]
                px, py = nx * iw, ny * ih
                if np.hypot(px - gx, py - gy) <= tol:
                    hit += 1
                    per_class_hit[c] = per_class_hit.get(c, 0) + 1
    print('日志: %s' % log)
    print('帧数: %d   GT 总点: %d' % (frames, tot))
    print('板端命中: %d/%d = %.2f%%' % (hit, tot, 100.0 * hit / max(tot, 1)))
    worst = sorted(range(NC), key=lambda c: (per_class_hit.get(c, 0) / max(per_class_cnt.get(c, 1), 1)))
    print('逐类命中率最低 8 个:', ', '.join(
        'cls%d:%.0f%%' % (c, 100.0 * per_class_hit.get(c, 0) / max(per_class_cnt.get(c, 1), 1))
        for c in worst[:8]))


if __name__ == '__main__':
    main()
