# -*- coding: utf-8 -*-
"""板端结果 GT 命中率评测（包内相对路径，自包含）

用法：
  python eval_board_gt.py                  # 两组都评
  python eval_board_gt.py --set philips
  python eval_board_gt.py --set toshiba --log board/logs/log_toshiba_a4c_54f_100mhz.txt
输出：sim/results/per_class_board_<set>.csv + 控制台指标
"""
import argparse
import csv
import os

import numpy as np
from PIL import Image

import paths
from generate_validation_results import parse_log, load_gt, DEDUPE_PX

NC = 36


def evaluate(key, log_path=None):
    cfg = paths.SETS[key]
    log = log_path or cfg['log']
    frames, _ = parse_log(log)
    hit = tot = 0
    cls_hit = np.zeros(NC)
    cls_cnt = np.zeros(NC)
    positions, confs = [], []
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
        positions.append(len(kept))
        confs.append(float(np.mean([v[2] for v in frames[f].values()])))
        for c, (cx, cy, bw, bh) in gt.items():
            gx, gy = cx * iw, cy * ih
            tol = max(bw * iw, bh * ih) / 2 + 4.0
            tot += 1
            cls_cnt[c] += 1
            if c in frames[f]:
                px, py = frames[f][c][0] * iw, frames[f][c][1] * ih
                if np.hypot(px - gx, py - gy) <= tol:
                    hit += 1
                    cls_hit[c] += 1

    out = os.path.join(paths.ensure_dir(paths.RESULTS), 'per_class_board_%s.csv' % key)
    with open(out, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['cls', 'gt_count', 'hit_count', 'hit_rate_percent'])
        for c in range(NC):
            rate = 100.0 * cls_hit[c] / cls_cnt[c] if cls_cnt[c] else 0.0
            w.writerow([c, int(cls_cnt[c]), int(cls_hit[c]), round(rate, 2)])

    print('[%s] log: %s' % (key, os.path.basename(log)))
    print('  frames=%d  positions/frame=%.1f  conf=%.3f' % (len(frames), np.mean(positions), np.mean(confs)))
    print('  GT hit: %d/%d = %.2f%%' % (hit, tot, 100.0 * hit / max(tot, 1)))
    print('  per-class CSV: %s' % out)
    return hit, tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--set', choices=['philips', 'toshiba', 'both'], default='both')
    ap.add_argument('--log', default=None)
    args = ap.parse_args()
    if not paths.check():
        print('ERROR: package paths incomplete')
        return 1
    keys = ['philips', 'toshiba'] if args.set == 'both' else [args.set]
    for k in keys:
        evaluate(k, args.log if len(keys) == 1 else None)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
