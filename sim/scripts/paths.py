# -*- coding: utf-8 -*-
"""包内相对路径常量（所有 sim 脚本共用，避免硬编码绝对路径）

目录约定：
    <package>/data/images_philips_a3c, data/labels_philips_a3c
    <package>/data/images_toshiba_a4c, data/labels_toshiba_a4c
    <package>/data/weights/logs_1019_best_epoch_weights.pth
    <package>/board/logs/log_*.txt
    <package>/sim/pc_reference/{nets,utils,model_data}
    <package>/sim/results/  (输出)
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(os.path.dirname(HERE))          # sim/scripts -> sim -> package root
DATA = os.path.join(PKG, 'data')
BOARD = os.path.join(PKG, 'board')
LOGS = os.path.join(BOARD, 'logs')
RESULTS = os.path.join(PKG, 'sim', 'results')
PCLIB = os.path.join(PKG, 'sim', 'pc_reference')
ANCHORS = os.path.join(PCLIB, 'model_data', 'yolo_anchors.txt')
WEIGHTS = os.path.join(DATA, 'weights', 'logs_1019_best_epoch_weights.pth')

SETS = {
    'philips': {
        'images': os.path.join(DATA, 'images_philips_a3c'),
        'labels': os.path.join(DATA, 'labels_philips_a3c'),
        'log': os.path.join(LOGS, 'log_philips_a3c_50f.txt'),
        'label_pattern': '%04d.txt',          # 0001.txt ...
    },
    'toshiba': {
        'images': os.path.join(DATA, 'images_toshiba_a4c'),
        'labels': os.path.join(DATA, 'labels_toshiba_a4c'),
        'log': os.path.join(LOGS, 'log_toshiba_a4c_54f.txt'),
        'label_pattern': 'g%d.txt',           # g0.txt ...
    },
}


def ensure_dir(p):
    os.makedirs(p, exist_ok=True)
    return p


def check(verbose=True):
    """打印关键路径存在性，便于排查"""
    items = [
        ('package root', PKG), ('data', DATA), ('board/logs', LOGS),
        ('pc_reference', PCLIB), ('anchors', ANCHORS), ('pytorch weights', WEIGHTS),
    ]
    ok = True
    for name, p in items:
        exists = os.path.exists(p)
        ok = ok and exists
        if verbose:
            print('  [%s] %-16s %s' % ('OK' if exists else 'MISS', name, p))
    for k, v in SETS.items():
        for key in ('images', 'labels', 'log'):
            if not os.path.exists(v[key]):
                ok = False
                if verbose:
                    print('  [MISS] %s.%s %s' % (k, key, v[key]))
    return ok


if __name__ == '__main__':
    print('package root:', PKG)
    print('all paths ok:', check())
