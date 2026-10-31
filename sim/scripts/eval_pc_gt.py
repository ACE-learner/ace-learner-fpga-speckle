# -*- coding: utf-8 -*-
"""PC 端 PyTorch 参考评测（包内自包含：模型代码 + 权重都在包里）

用法：
  python eval_pc_gt.py                    # 两组都评
  python eval_pc_gt.py --set philips
  python eval_pc_gt.py --set toshiba --weights ../data/weights/logs_1019_best_epoch_weights.pth
输出：sim/results/per_frame_pc_<set>.csv + 控制台指标

预处理必须与板端一致：RGB -> BICUBIC 416x416 -> /255 -> CHW
"""
import argparse
import csv
import os
import sys

import numpy as np
from PIL import Image

import paths

NC, MASK = 36, [[3, 4, 5], [1, 2, 3]]
CONF, NMS = 0.05, 0.3


def load_net(weights_path):
    if not os.path.exists(weights_path):
        raise FileNotFoundError('weights not found: %s' % weights_path)
    sys.path.insert(0, paths.PCLIB)
    import torch
    from nets.yolo import YoloBody
    from utils.utils import get_anchors
    from utils.utils_bbox import DecodeBox
    anchors, _ = get_anchors(paths.ANCHORS)
    bu = DecodeBox(anchors, NC, (416, 416), MASK)
    net = YoloBody(MASK, NC, phi=0, pretrained=False)
    state = torch.load(weights_path, map_location='cpu')
    if isinstance(state, dict) and 'state_dict' in state:
        state = state['state_dict']
    net.load_state_dict(state, strict=True)
    net.eval()
    return torch, bu, net


def encode_image(path):
    """与板端一致的预处理"""
    img = Image.open(path).convert('RGB')
    w, h = img.size
    r = img.resize((416, 416), Image.BICUBIC)
    arr = np.array(r, dtype=np.float32) / 255.0
    chw = np.transpose(arr, (2, 0, 1))[None, ...]
    return chw, (w, h)


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


def eval_set(key, torch, bu, net):
    cfg = paths.SETS[key]
    names = sorted(f for f in os.listdir(cfg['images']) if f.startswith('img') and f.endswith('.png'))
    names.sort(key=lambda s: int(''.join(ch for ch in s if ch.isdigit()) or 0))
    hit = tot = 0
    rows = []
    kps, confs = [], []
    for idx, name in enumerate(names):
        chw, (iw, ih) = encode_image(os.path.join(cfg['images'], name))
        inp = torch.from_numpy(chw.copy())
        with torch.no_grad():
            p0, p1 = net(inp)
            outs = bu.decode_box([p0, p1])
            res = bu.non_max_suppression(torch.cat(outs, 1), NC, (416, 416), np.array([ih, iw]),
                                         False, conf_thres=CONF, nms_thres=NMS)
        kp = {}
        if res[0] is not None:
            for row in res[0]:
                c = int(row[6]); s = float(row[4] * row[5])
                if c not in kp or s > kp[c][1]:
                    kp[c] = (((float(row[1]) + float(row[3])) / 2,
                              (float(row[0]) + float(row[2])) / 2), s)
        kps.append(len(kp))
        confs.append(float(np.mean([v[1] for v in kp.values()])) if kp else 0.0)
        gt = load_gt(cfg['labels'], cfg['label_pattern'], idx)
        h = 0
        for c, (cx, cy, bw, bh) in gt.items():
            gx, gy = cx * iw, cy * ih
            tol = max(bw * iw, bh * ih) / 2 + 4.0
            tot += 1
            if c in kp and np.hypot(kp[c][0][0] - gx, kp[c][0][1] - gy) <= tol:
                hit += 1
                h += 1
        rows.append((idx, len(kp), len(gt), h, round(confs[-1], 3)))

    out = os.path.join(paths.ensure_dir(paths.RESULTS), 'per_frame_pc_%s.csv' % key)
    with open(out, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['frame', 'keypoints', 'gt_points', 'gt_hits', 'mean_conf'])
        w.writerows(rows)
    print('[%s] frames=%d  keypoints/frame=%.1f  conf=%.3f  GT hit=%d/%d = %.2f%%'
          % (key, len(rows), np.mean(kps), np.mean(confs), hit, tot, 100.0 * hit / max(tot, 1)))
    print('  per-frame CSV: %s' % out)
    return hit, tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--set', choices=['philips', 'toshiba', 'both'], default='both')
    ap.add_argument('--weights', default=paths.WEIGHTS)
    args = ap.parse_args()
    if not paths.check():
        print('ERROR: package paths incomplete')
        return 1
    try:
        torch, bu, net = load_net(args.weights)
    except ImportError:
        print('ERROR: 需要安装 PyTorch（pip install torch --index-url https://download.pytorch.org/whl/cpu）')
        return 2
    keys = ['philips', 'toshiba'] if args.set == 'both' else [args.set]
    for k in keys:
        eval_set(k, torch, bu, net)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
