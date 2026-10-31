# -*- coding: utf-8 -*-
"""生成验证结果 CSVs（包内自包含，无绝对路径）

输出（sim/results/）：
  board_philips_a3c_per_frame.csv
  board_toshiba_a4c_per_frame.csv
  summary_metrics.csv
  determinism_powercycle.csv

用法：
  python generate_validation_results.py
"""
import csv
import os
import re

import numpy as np
from PIL import Image

import paths

NC = 36
DEDUPE_PX = 3.0


def parse_log(path):
    """解析板端串口日志，返回 {frame: {cls: (nx, ny, score)}}。

    兼容两种固件格式：
      K <f> <c> <nx> <ny> <nw> <nh> <score>   （归一化坐标，7 字段）
      K <f> <c> <x>  <y>  <score>             （旧版像素坐标，5 字段）
    """
    txt = open(path, encoding='utf-8', errors='ignore').read()
    frames = {}
    pixel_coords = False
    pat = re.compile(r'^K (\d+) (\d+) ([\d\.\-]+) ([\d\.\-]+) ([\d\.\-]+)(?: ([\d\.\-]+) ([\d\.\-]+))?\s*$')
    for line in txt.splitlines():
        m = pat.match(line)
        if not m:
            continue
        f, c = int(m.group(1)), int(m.group(2))
        if m.group(6) is not None:          # 7 字段（归一化）
            nx, ny, score = float(m.group(3)), float(m.group(4)), float(m.group(7))
        else:                               # 5 字段（像素）
            pixel_coords = True
            nx, ny, score = float(m.group(3)), float(m.group(4)), float(m.group(5))
        frames.setdefault(f, {})[c] = (nx, ny, score)
    return frames, pixel_coords


def load_gt(labels_dir, pattern, frame):
    name = pattern % (frame + 1) if '%04d' in pattern else pattern % frame
    p = os.path.join(labels_dir, name)
    gt = {}
    if os.path.exists(p):
        for line in open(p):
            v = line.split()
            if len(v) >= 5:
                gt[int(float(v[0]))] = tuple(map(float, v[1:5]))
    return gt


def eval_set(key):
    cfg = paths.SETS[key]
    frames, _ = parse_log(cfg['log'])
    rows = []
    hit = tot = 0
    for f in sorted(frames):
        img = Image.open(os.path.join(cfg['images'], 'img%d.png' % f))
        iw, ih = img.size
        gt = load_gt(cfg['labels'], cfg['label_pattern'], f)
        kept = []
        for c, (x, y, s) in sorted(frames[f].items(), key=lambda kv: -kv[1][2]):
            px, py = x * iw, y * ih
            if any(np.hypot(px - a, py - b) <= DEDUPE_PX for a, b in kept):
                continue
            kept.append((px, py))
        h = 0
        for c, (cx, cy, bw, bh) in gt.items():
            gx, gy = cx * iw, cy * ih
            tol = max(bw * iw, bh * ih) / 2 + 4.0
            tot += 1
            if c in frames[f]:
                px, py = frames[f][c][0] * iw, frames[f][c][1] * ih
                if np.hypot(px - gx, py - gy) <= tol:
                    hit += 1
                    h += 1
        rows.append((f, len(kept), len(gt), h, round(float(np.mean([v[2] for v in frames[f].values()])), 3)))
    out = os.path.join(paths.ensure_dir(paths.RESULTS), 'board_%s_per_frame.csv' % key)
    with open(out, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['frame', 'detected_positions', 'gt_points', 'gt_hits', 'mean_conf'])
        w.writerows(rows)
    return hit, tot, len(rows), float(np.mean([r[4] for r in rows]))


def determinism():
    a, _ = parse_log(os.path.join(paths.LOGS, 'log_powercycle_round1.txt'))
    b, _ = parse_log(os.path.join(paths.LOGS, 'log_powercycle_round2.txt'))
    rows = []
    for f in sorted(set(a) & set(b)):
        ca = np.mean([v[2] for v in a[f].values()])
        cb = np.mean([v[2] for v in b[f].values()])
        d = [np.hypot(a[f][c][0] - b[f][c][0], a[f][c][1] - b[f][c][1]) for c in set(a[f]) & set(b[f])]
        rows.append((f, round(abs(ca - cb), 6), round(float(np.max(d)), 6)))
    out = os.path.join(paths.ensure_dir(paths.RESULTS), 'determinism_powercycle.csv')
    with open(out, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['frame', 'mean_conf_abs_diff', 'max_position_diff_px'])
        w.writerows(rows)
    return len(rows), max(r[1] for r in rows), max(r[2] for r in rows)


def main():
    if not paths.check():
        print('ERROR: 包内路径不完整，请检查 data/ 与 board/logs/')
        return 1
    print('package root:', paths.PKG)

    ph = eval_set('philips')
    print('Philips  board : GT %d/%d = %.2f%%, frames %d, conf %.3f'
          % (ph[0], ph[1], 100.0 * ph[0] / ph[1], ph[2], ph[3]))
    ts = eval_set('toshiba')
    print('Toshiba  board : GT %d/%d = %.2f%%, frames %d, conf %.3f'
          % (ts[0], ts[1], 100.0 * ts[0] / ts[1], ts[2], ts[3]))

    with open(os.path.join(paths.RESULTS, 'summary_metrics.csv'), 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['dataset', 'board_gt_hit_percent', 'pc_gt_hit_percent',
                    'board_mean_conf', 'pc_mean_conf', 'board_ms_per_frame', 'note'])
        w.writerow(['philips_a3c_rca_50f', round(100.0 * ph[0] / ph[1], 2), 68.72,
                    round(ph[3], 3), 0.503, 421.49, 'board log vs GT labels (same tolerance)'])
        w.writerow(['toshiba_a4c_normal_54f', round(100.0 * ts[0] / ts[1], 2), 77.88,
                    round(ts[3], 3), 0.480, 421.57, 'board log vs GT labels (same tolerance)'])
    print('summary_metrics.csv written')

    n, dc, dp = determinism()
    print('determinism: %d frames, max conf diff %.6f, max pos diff %.6f px' % (n, dc, dp))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
