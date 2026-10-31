# -*- coding: utf-8 -*-
"""把任意文件夹的图片编码成板端输入：img0.bin / img0.png ... + img_num.txt"""
import os
import re
import sys

import numpy as np
from PIL import Image

src = sys.argv[1]
dst = sys.argv[2]
maxn = int(sys.argv[3]) if len(sys.argv) > 3 else 200
exts = ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff')

os.makedirs(dst, exist_ok=True)
def _natkey(name):
    """自然排序：img2 < img10（避免字典序把 img10 排到 img2 前面）"""
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r'(\d+)', name)]


files = sorted([f for f in os.listdir(src) if f.lower().endswith(exts)], key=_natkey)[:maxn]
if not files:
    print('[ERROR] 源文件夹里没有图片:', src)
    sys.exit(1)

for i, f in enumerate(files):
    im = Image.open(os.path.join(src, f)).convert('RGB')
    im.save(os.path.join(dst, 'img%d.png' % i))
    r = im.resize((416, 416), Image.BICUBIC)
    arr = np.array(r, dtype=np.float32) / 255.0
    chw = np.transpose(arr, (2, 0, 1)).astype('<f4')
    chw.tofile(os.path.join(dst, 'img%d.bin' % i))
    if (i + 1) % 20 == 0:
        print('  编码 %d/%d' % (i + 1, len(files)))

with open(os.path.join(dst, 'img_num.txt'), 'w') as fh:
    fh.write(str(len(files)))

import datetime
with open(os.path.join(dst, 'set_info.txt'), 'w', encoding='utf-8') as fh:
    fh.write('count=%d\ncreated=%s\nsrc=%s\n' % (len(files), datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), src))

print('完成: %d 张 -> %s' % (len(files), dst))
print('img0.bin 大小: %d B (应为 2076672)' % os.path.getsize(os.path.join(dst, 'img0.bin')))
