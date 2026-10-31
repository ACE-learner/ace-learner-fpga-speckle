#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用板端 out0_N.bin / out1_N.bin 解码并画图（诚实版）

与旧版的区别：
  1) 不再把"36 个类"当成"36 个点"：按像素距离合并同一位置的多个类（默认 3 px）
  2) header 显示实际检测到的不同位置数：detected N/36 positions (merged M dup)
  3) 置信度阈值可配（--conf，默认 0.05），过滤明显噪声
  4) 标签默认只显示类号（--label conf 可显示"类号+置信度"）
  5) 合并时保留置信度最高的类作为代表，其余只在统计里计入 merged

用法：
  python decode_sd_outputs.py <out文件目录> <原始图片目录> <输出目录>
  python decode_sd_outputs.py <out目录> <img目录> <输出目录> --conf 0.05 --merge-px 3 --label conf
"""
import argparse
import colorsys
import glob
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

CLASS_COUNT = 36
ATTRIBUTES = 5 + CLASS_COUNT
ANCHORS = np.array(
    [[10.0, 14.0], [23.0, 27.0], [37.0, 58.0],
     [81.0, 82.0], [135.0, 169.0], [344.0, 319.0]],
    dtype=np.float32,
)
HEADS = ((13, (3, 4, 5)), (26, (1, 2, 3)))


def sigmoid(values):
    positive = values >= 0.0
    result = np.empty_like(values, dtype=np.float32)
    result[positive] = 1.0 / (1.0 + np.exp(-values[positive]))
    exp_values = np.exp(values[~positive])
    result[~positive] = exp_values / (1.0 + exp_values)
    return result


def read_head(path, grid):
    expected = 3 * ATTRIBUTES * grid * grid
    data = np.fromfile(path, dtype='<f4')
    if data.size != expected:
        raise ValueError('%s has %d float32 values; expected %d.' % (path, data.size, expected))
    return data.reshape(3, ATTRIBUTES, grid, grid)


def extract_keypoints(out0, out1):
    """YOLO 标准解码（与原工程 yolo2.py 口径一致）：

    每个预测框先取类别 = 36 类中的 argmax（一个框只属于一个类），
    再按类保留最高分框。实测 GT 命中 77.88%（与原版 NMS 口径相同）；
    旧实现"按类独立 argmax"会抢到别的类的框，只有 74.23%。
    """
    best_scores = np.full(CLASS_COUNT, -1.0, dtype=np.float32)
    best_meta = [None] * CLASS_COUNT

    for head_index, (features, (grid, anchor_mask)) in enumerate(((out0, HEADS[0]), (out1, HEADS[1]))):
        plane = grid * grid
        obj = sigmoid(features[:, 4].reshape(3, plane))                    # (3, plane)
        cls = sigmoid(features[:, 5:].reshape(3, CLASS_COUNT, plane))      # (3, NC, plane)
        cls_max = cls.max(axis=1)                                         # (3, plane)
        cls_idx = cls.argmax(axis=1)                                      # (3, plane)
        score = obj * cls_max                                             # (3, plane)
        for cls_id in range(CLASS_COUNT):
            cand = np.where(cls_idx == cls_id, score, -1.0).reshape(-1)
            flat = int(cand.argmax())
            s = float(cand[flat])
            if s <= best_scores[cls_id]:
                continue
            anchor = flat // plane
            pos = flat % plane
            best_scores[cls_id] = s
            best_meta[cls_id] = (head_index, grid, anchor_mask, anchor, pos)

    raw = []
    for cls, score in enumerate(best_scores):
        if score < 0.0:
            continue
        head_index, grid, anchor_mask, anchor, pos = best_meta[cls]
        features = out0 if head_index == 0 else out1
        gy, gx = divmod(pos, grid)
        tx, ty, tw, th = features[anchor, 0:4, gy, gx]
        anchor_index = anchor_mask[anchor]
        nx = float((sigmoid(np.array([tx]))[0] + gx) / grid)
        ny = float((sigmoid(np.array([ty]))[0] + gy) / grid)
        nw = float(np.exp(np.clip(tw, -20.0, 20.0)) * ANCHORS[anchor_index, 0] / 416.0)
        nh = float(np.exp(np.clip(th, -20.0, 20.0)) * ANCHORS[anchor_index, 1] / 416.0)
        raw.append((cls, nx, ny, nw, nh, float(score)))
    return raw


def merge_by_position(points, width, height, merge_px):
    """按像素距离合并同一位置的多个类，保留最高分的类作为代表。

    返回：kept（代表点列表）、merged_count（被合并掉的类数）
    """
    order = sorted(points, key=lambda p: -p[5])
    kept, merged = [], 0
    for p in order:
        x, y = p[1] * width, p[2] * height
        if any(np.hypot(x - k[1] * width, y - k[2] * height) <= merge_px for k in kept):
            merged += 1
            continue
        kept.append(p)
    kept.sort(key=lambda p: p[0])
    return kept, merged


def draw_frame(image_path, output_path, points, args):
    image = Image.open(image_path).convert('RGB')
    width, height = image.size
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype('simhei.ttf', 12)
    except Exception:
        font = ImageFont.load_default()
    colors = [tuple(int(v * 255) for v in colorsys.hsv_to_rgb(cls / CLASS_COUNT, 0.95, 1.0))
              for cls in range(CLASS_COUNT)]

    # 1) 置信度过滤
    total_points = len(points)
    pts = [p for p in points if p[5] >= args.conf]
    filtered = total_points - len(pts)
    # 2) 按位置合并
    kept, merged = merge_by_position(pts, width, height, args.merge_px)

    # 3) 相邻类连线（仅代表点之间）
    for a, b in zip(kept, kept[1:]):
        if b[0] == a[0] + 1:
            draw.line((a[1] * width, a[2] * height, b[1] * width, b[2] * height),
                      fill=(255, 215, 0), width=2)

    # 4) 每个位置只画一个框 + 十字 + 类号
    for cls, nx, ny, nw, nh, score in kept:
        x, y = nx * width, ny * height
        half_w, half_h = nw * width / 2.0, nh * height / 2.0
        draw.rectangle((x - half_w, y - half_h, x + half_w, y + half_h), outline=colors[cls], width=2)
        draw.line((x - 4, y, x + 4, y), fill=(0, 255, 0), width=1)
        draw.line((x, y - 4, x, y + 4), fill=(0, 255, 0), width=1)
        label = str(cls) if args.label == 'cls' else '%d %.2f' % (cls, score)
        draw.text((x + 5, y - 13), label, font=font, fill=(255, 255, 255))

    # 5) 诚实统计：实际不同位置数 / 类别总数
    n_pos = len(kept)
    mean_conf = float(np.mean([p[5] for p in kept])) if kept else 0.0
    frame_id = os.path.basename(image_path)[3:-4]
    header = ('img%s  detected %d/%d positions (merged %d dup, conf-filtered %d)  mean conf %.2f'
              % (frame_id, n_pos, CLASS_COUNT, merged, filtered, mean_conf))
    draw.rectangle((0, 0, min(width, 640), 18), fill=(0, 0, 0))
    draw.text((5, 3), header, font=font, fill=(0, 255, 0))
    image.save(output_path)
    return n_pos, merged, mean_conf


def main():
    ap = argparse.ArgumentParser(description='Decode FPGA out files and render honest keypoint result images')
    ap.add_argument('raw_dir', help='包含 out0_N.bin / out1_N.bin 的目录')
    ap.add_argument('image_dir', help='原始图片目录（imgN.png）')
    ap.add_argument('output_dir', help='输出目录')
    ap.add_argument('--conf', type=float, default=0.05, help='置信度阈值（默认 0.05）')
    ap.add_argument('--merge-px', type=float, default=3.0, help='同位置合并距离（像素，默认 3）')
    ap.add_argument('--label', choices=['cls', 'conf'], default='cls', help='标签内容')
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    frame_ids = []
    for path in glob.glob(os.path.join(args.raw_dir, 'out0_*.bin')):
        m = re.fullmatch(r'out0_(\d+)\.bin', os.path.basename(path))
        if m and os.path.isfile(os.path.join(args.raw_dir, 'out1_%s.bin' % m.group(1))):
            frame_ids.append(int(m.group(1)))
    frame_ids.sort()
    if not frame_ids:
        raise SystemExit('No paired out0_N.bin/out1_N.bin files found in: %s' % args.raw_dir)

    rendered, stats = [], []
    for frame in frame_ids:
        image_path = os.path.join(args.image_dir, 'img%d.png' % frame)
        if not os.path.isfile(image_path):
            print('Skipping img%d: original image is absent.' % frame)
            continue
        out0 = read_head(os.path.join(args.raw_dir, 'out0_%d.bin' % frame), 13)
        out1 = read_head(os.path.join(args.raw_dir, 'out1_%d.bin' % frame), 26)
        out_path = os.path.join(args.output_dir, 'result_img%d.png' % frame)
        n_pos, merged, mc = draw_frame(image_path, out_path, extract_keypoints(out0, out1), args)
        rendered.append(out_path)
        stats.append((frame, n_pos, merged, mc))

    if not rendered:
        raise SystemExit('No output frame has a matching original image.')

    print('Rendered %d frames -> %s' % (len(rendered), args.output_dir))
    print('positions/frame : mean %.1f (min %d, max %d)'
          % (np.mean([s[1] for s in stats]), min(s[1] for s in stats), max(s[1] for s in stats)))
    print('merged dup/frame: mean %.1f' % np.mean([s[2] for s in stats]))
    print('mean conf       : %.3f' % np.mean([s[3] for s in stats]))
    print('note: %d/%d = detected distinct positions, NOT class count (%d classes total)'
          % (int(np.mean([s[1] for s in stats])), CLASS_COUNT, CLASS_COUNT))

    frames = [Image.open(p).convert('RGB') for p in rendered]
    h = 360
    w = max(1, int(frames[0].width * h / frames[0].height))
    previews = [f.resize((w, h)) for f in frames]
    previews[0].save(os.path.join(args.output_dir, 'demo.gif'), save_all=True,
                     append_images=previews[1:], duration=150, loop=0, optimize=True)


if __name__ == '__main__':
    main()
