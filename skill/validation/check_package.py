# -*- coding: utf-8 -*-
"""验证工程包完整性 + 关键指标是否符合预期（仅用标准库，任何 Python 3 可运行）

用法:
    python check_package.py [package_root]
退出码: 0 = 全部通过；1 = 有失败项
"""
import csv
import os
import re
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok), detail))
    print(('  PASS  ' if ok else '  FAIL  ') + name + ('   [' + detail + ']' if detail else ''))


def count(path, pattern=None):
    if not os.path.isdir(path):
        return -1
    files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
    if pattern:
        files = [f for f in files if re.search(pattern, f)]
    return len(files)


print('package root:', ROOT)

# ---------- 1) 目录结构 ----------
print('\n[1] directory structure')
for d in ['src/hls', 'src/rtl', 'src/software', 'src/vivado', 'sim/scripts', 'sim/results',
          'build', 'board/bitstream', 'board/scripts', 'board/logs', 'board/results',
          'data/images_philips_a3c', 'data/labels_philips_a3c',
          'data/images_toshiba_a4c', 'data/labels_toshiba_a4c',
          'data/reference_results', 'skill', 'skill/validation', 'report']:
    check('dir exists: ' + d, os.path.isdir(os.path.join(ROOT, d)))

# ---------- 2) 关键产物 ----------
print('\n[2] key artifacts')
for f in ['README.md', 'ENVIRONMENT.md', 'requirements.txt',
          'sim/scripts/paths.py', 'sim/pc_reference/nets/yolo.py',
          'sim/pc_reference/model_data/yolo_anchors.txt',
          'src/software/main.cpp', 'src/software/debug.cpp', 'src/software/sd_io.cpp',
          'src/hls/std_conv.h', 'board/sd_boot_image.zip', 'board/bitstream/system_wrapper.bit', 'board/weights/sd_weights_oct20.zip',
          'board/bitstream/yolov4_tiny.elf', 'build/implementation_report.md',
          'sim/results/summary_metrics.csv', 'skill/README.md',
          'report/design_report.md', 'report/llm_collaboration_record.md']:
    check('file exists: ' + f, os.path.isfile(os.path.join(ROOT, f)))

# ---------- 3) 源码内容关键标记 ----------
print('\n[3] source content markers')
hls_h = os.path.join(ROOT, 'src', 'hls', 'std_conv.h')
if os.path.isfile(hls_h):
    txt = open(hls_h, encoding='utf-8', errors='ignore').read()
    check('hls uses ap_fixed<16,7>', 'ap_fixed<16,7' in txt)
sd = os.path.join(ROOT, 'src', 'software', 'sd_io.h')
if os.path.isfile(sd):
    t2 = open(sd, encoding='utf-8', errors='ignore').read()
    check('software defines SCALE 512', 'SCALE' in t2 and '512' in t2)
sw = os.path.join(ROOT, 'src', 'software', 'debug.cpp')
if os.path.isfile(sw):
    txt = open(sw, encoding='utf-8', errors='ignore').read()
    check('software has keypoint postprocess', 'KP_NC' in txt and 'K ' in txt)
    check('software uses FatFS f_open (not fopen)', 'f_open' in txt)
    check('software prints ALL DONE', 'ALL DONE' in txt)

# ---------- 4) 数据 ----------
print('\n[4] data')
n = count(os.path.join(ROOT, 'data', 'images_philips_a3c'), r'^img\d+\.png$')
check('philips images == 50', n == 50, 'got %d' % n)
n = count(os.path.join(ROOT, 'data', 'labels_philips_a3c'), r'^\d{4}\.txt$')
check('philips labels == 50', n == 50, 'got %d' % n)
n = count(os.path.join(ROOT, 'data', 'images_toshiba_a4c'), r'^img\d+\.png$')
check('toshiba images == 54', n == 54, 'got %d' % n)
n = count(os.path.join(ROOT, 'data', 'labels_toshiba_a4c'), r'^g\d+\.txt$')
check('toshiba labels == 54', n == 54, 'got %d' % n)

# ---------- 5) 日志 ----------
print('\n[5] board logs')
for name, frames in [('log_philips_a3c_50f.txt', 50), ('log_toshiba_a4c_54f.txt', 54)]:
    p = os.path.join(ROOT, 'board', 'logs', name)
    if not os.path.isfile(p):
        check('log exists: ' + name, False)
        continue
    txt = open(p, encoding='utf-8', errors='ignore').read()
    ids = {}
    for m in re.finditer(r'(?m)^KP (\d+) ', txt):
        ids[m.group(1)] = 1
    check('%s frames == %d' % (name, frames), len(ids) == frames, 'got %d' % len(ids))
    check('%s has 36/36' % name, '36/36' in txt)
    # 结束标记：新版固件才有 ALL DONE；旧日志用帧数判断即可
    if frames == 50:
        check('%s has ALL DONE' % name, 'ALL DONE' in txt)

# ---------- 6) 指标 ----------
print('\n[6] metrics (from sim/results/summary_metrics.csv)')
p = os.path.join(ROOT, 'sim', 'results', 'summary_metrics.csv')
if os.path.isfile(p):
    rows = list(csv.DictReader(open(p, encoding='utf-8-sig')))
    got = {r['dataset']: float(r['board_gt_hit_percent']) for r in rows}
    check('philips board GT hit in [64,70]', 64 <= got.get('philips_a3c_rca_50f', -1) <= 70,
          'got %s' % got.get('philips_a3c_rca_50f'))
    check('toshiba board GT hit in [70,78]', 70 <= got.get('toshiba_a4c_normal_54f', -1) <= 78,
          'got %s' % got.get('toshiba_a4c_normal_54f'))
    ok = True
    for r in rows:
        if 'newrule' in r['dataset'] and abs(float(r['board_ms_per_frame']) - 496.6) > 8:
            ok = False
    check('inference ~496.6 ms/frame (100MHz)', ok)

# ---------- 7) 结果图 ----------
print('\n[7] result images')
n = count(os.path.join(ROOT, 'board', 'results'))
check('result images >= 1', n >= 1, 'got %d' % n)

# ---------- 汇总 ----------
bad = [r for r in results if not r[1]]
print('\n===== SUMMARY: %d checks, %d passed, %d failed =====' % (len(results), len(results) - len(bad), len(bad)))
if bad:
    for name, _, detail in bad:
        print('  FAILED:', name, detail)
    sys.exit(1)
print('ALL CHECKS PASSED')
sys.exit(0)
