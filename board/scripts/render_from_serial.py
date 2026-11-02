# -*- coding: utf-8 -*-
"""把板端串口日志（归一化坐标）画到图片上，原版样式（去重）
用法: python render_from_serial.py <serial_log> <images_dir> <out_dir>
"""
import colorsys
import glob
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

LOG = sys.argv[1]
IMGDIR = sys.argv[2]
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = sys.argv[3] if len(sys.argv) > 3 else os.path.join(PROJECT_ROOT, '06_文档与结果', 'rendered_results')
FONT = os.environ.get('FPGA_RENDER_FONT', '')
NC = 36
CLUSTER_PX = 3.0
PARTIAL_MIN = 28   # 单帧类别数少于此值，视为串口截断，不渲染（正常 33~36 类/帧）

os.makedirs(OUT, exist_ok=True)

txt = open(LOG, encoding='utf-8', errors='ignore').read()
board = {}
for m in re.finditer(r'K (\d+) (\d+) ([\d\.]+) ([\d\.]+) ([\d\.]+) ([\d\.]+) ([\d\.]+)', txt):
    f, c = int(m.group(1)), int(m.group(2))
    board.setdefault(f, {})[c] = (float(m.group(3)), float(m.group(4)),
                                  float(m.group(5)), float(m.group(6)), float(m.group(7)))
if not board:
    print('[ERROR] 日志里没有关键点数据（K 行）。日志:', LOG)
    if ('writing yolo_test' in txt) or ('time elapsed is' in txt):
        print('[HINT] 该日志来自旧固件（SD 卡 out 文件模式）：只有 image/time elapsed 和 writing out 行，没有 K 行。')
        print('       解决办法二选一：')
        print('         1) 改用 Decode-SD-Outputs.bat 解 out 文件出图（旧固件路径）；')
        print('         2) 把 SD 卡 BOOT.bin 换成新版（01_免重建运行\\BOOT.bin）后重新跑，串口就会有 K 行。')
    else:
        print('[HINT] 请确认：抓串口时板子确实在运行、串口是 115200、固件为新版（应出现 KPT/KP/K 行）。')
    sys.exit(1)

try:
    fs = ImageFont.truetype(FONT, 11)
    fh = ImageFont.truetype(FONT, 13)
except Exception:
    fs = fh = ImageFont.load_default()

colors = [tuple(int(v * 255) for v in colorsys.hsv_to_rgb(c / NC, 0.95, 1.0)) for c in range(NC)]

_IMG_EXTS = ('.png', '.jpg', '.jpeg', '.bmp')
_img_cache = None


def _natkey(name):
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r'(\d+)', name)]


def _image_list():
    global _img_cache
    if _img_cache is None:
        files = [f for f in os.listdir(IMGDIR) if f.lower().endswith(_IMG_EXTS)]
        _img_cache = sorted(files, key=_natkey)
    return _img_cache


def image_path(f):
    """优先 img<N>.png；否则按自然排序取第 N 张（支持 0001.png 等命名）"""
    p0 = os.path.join(IMGDIR, 'img%d.png' % f)
    if os.path.exists(p0):
        return p0
    lst = _image_list()
    if 0 <= f < len(lst):
        return os.path.join(IMGDIR, lst[f])
    return p0



counts = []
skipped = []
missing = []
for f in sorted(board):
    p = image_path(f)
    if not os.path.exists(p):
        missing.append(f)
        continue
    img = Image.open(p).convert('RGB')
    iw, ih = img.size
    kp = board[f]

    pts = [(c, kp[c][0] * iw, kp[c][1] * ih, kp[c][2] * iw, kp[c][3] * ih, kp[c][4]) for c in sorted(kp)]
    pts.sort(key=lambda t: -t[5])
    clusters = []
    for c, x, y, w, h, s in pts:
        placed = False
        for cl in clusters:
            if np.hypot(x - cl[1], y - cl[2]) <= CLUSTER_PX:
                cl[6].append(c)
                placed = True
                break
        if not placed:
            clusters.append([c, x, y, w, h, s, [c]])
    clusters.sort(key=lambda cl: cl[0])

    d = ImageDraw.Draw(img)
    for a, b in zip(clusters, clusters[1:]):
        if b[0] == a[0] + 1:
            d.line([a[1], a[2], b[1], b[2]], fill=(255, 215, 0), width=2)

    for c, x, y, w, h, s, members in clusters:
        d.rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], outline=colors[c], width=2)
        d.line([x - 4, y, x + 4, y], fill=(0, 255, 0), width=1)
        d.line([x, y - 4, x, y + 4], fill=(0, 255, 0), width=1)
        d.text((x + 5, y - 14), str(c), font=fs, fill=(255, 255, 255))

    npos = len(clusters)
    n_classes = len(kp)
    if n_classes < PARTIAL_MIN:
        print('[WARN] 帧 %d 只有 %d 个类别（< %d），疑似串口抓取截断，已跳过该帧渲染。' % (f, n_classes, PARTIAL_MIN))
        print('       原因：Read-Serial 在板子开始跑之后才打开串口，开头帧被截断；')
        print('       正确做法：先运行 Read-Serial.bat，看到"已打开串口"后，再复位/上电板子。')
        skipped.append((f, n_classes))
        continue
    merged = sum(len(cl[6]) - 1 for cl in clusters)
    mc = float(np.mean([cl[5] for cl in clusters]))
    header = 'img%d  detected %d/%d positions (merged %d)  mean conf %.2f' % (f, npos, NC, merged, mc)
    d.rectangle([0, 0, 520, 20], fill=(0, 0, 0))
    d.text((6, 3), header, font=fh, fill=(0, 255, 0))
    img.save(os.path.join(OUT, 'result_img%d.png' % f))
    counts.append(npos)

if missing:
    print('[WARN] 缺少图片的帧: %s' % ','.join(str(x) for x in missing[:20]))
if not counts:
    print('[ERROR] 没有渲染出任何帧：日志帧号与图片目录不匹配。')
    print('        日志: %s' % LOG)
    print('        图片目录: %s' % IMGDIR)
    print('        请确认图片目录就是 SD 卡测试集的那一批（可传第三个参数指定）。')
    sys.exit(2)

print('渲染帧数:', len(counts))
print('每帧不同位置数: 平均 %.1f（min %d / max %d）' % (np.mean(counts), min(counts), max(counts)))
print('输出:', OUT)

# GIF
frames = [Image.open(os.path.join(OUT, 'result_img%d.png' % i)).convert('RGB')
          for i in sorted(board) if os.path.exists(os.path.join(OUT, 'result_img%d.png' % i))]
if skipped:
    print('跳过截断帧:', ', '.join('img%d(%d类)' % s for s in skipped))
if frames:
    h = 360
    w = int(frames[0].width * h / frames[0].height)
    small = [im.resize((w, h)) for im in frames]
    g = os.path.join(OUT, 'demo.gif')
    small[0].save(g, save_all=True, append_images=small[1:], duration=150, loop=0, optimize=True)
    print('GIF:', g)

