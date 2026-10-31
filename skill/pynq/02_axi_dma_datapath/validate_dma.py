# -*- coding: utf-8 -*-
"""DMA 稳定性自检：多次传输一致性 + 吞吐统计 -> CSV

用法（板端）：
    python validate_dma.py --bit my.bit --dma axi_dma_0 --n 4096 --repeat 100
用法（PC 离线）：
    python validate_dma.py --mock --repeat 20 --csv dma_validate.csv
退出码：0 全一致；1 出现不一致或异常
"""
import argparse
import csv
import sys
import time

import numpy as np

from dma_loopback import make_pattern, sync_to_dev, sync_from_dev, dma_roundtrip_once


def run_board(args):
    from pynq import Overlay, allocate
    ol = Overlay(args.bit)
    dma = getattr(ol, args.dma)
    dtype = np.dtype(args.dtype)
    src = allocate(shape=(args.n,), dtype=dtype)
    dst = allocate(shape=(args.n,), dtype=dtype)
    pattern = make_pattern(args.n, dtype)
    rows = []
    ok = 0
    for i in range(args.repeat):
        src[:] = pattern
        sync_to_dev(src)
        dt = dma_roundtrip_once(dma, src, dst)
        sync_from_dev(dst)
        same = bool(np.array_equal(np.asarray(dst), pattern))
        ok += int(same)
        rows.append((i, round(dt * 1e3, 4), round(args.n * dtype.itemsize / dt / 1e6, 2), int(same)))
    write_csv(args.csv, rows)
    print_summary(rows, ok, args)
    return 0 if ok == args.repeat else 1


def run_mock(args):
    pattern = make_pattern(args.n, np.dtype(args.dtype))
    rows = []
    ok = 0
    for i in range(args.repeat):
        t = 0.0004 + (i % 7) * 2e-6
        # 模拟：前 90% 正确，制造一次不一致验证检出能力
        same = 1 if i != args.repeat - 1 else 0
        ok += same
        rows.append((i, round(t * 1e3, 4), round(args.n * pattern.dtype.itemsize / t / 1e6, 2), same))
    write_csv(args.csv, rows)
    print_summary(rows, ok, args, mock=True)
    # mock 期望：能检出最后一条不一致（ok == repeat-1）
    print('mock self-check:', 'PASS' if ok == args.repeat - 1 else 'FAIL')
    return 0 if ok == args.repeat - 1 else 1


def write_csv(path, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['iter', 'latency_ms', 'throughput_MBps', 'matched'])
        w.writerows(rows)
    print('CSV written:', path)


def print_summary(rows, ok, args, mock=False):
    lat = np.array([r[1] for r in rows])
    thr = np.array([r[2] for r in rows])
    print('repeat=%d  ok=%d/%d  latency p50=%.3f ms p90=%.3f ms  throughput p50=%.1f MB/s'
          % (len(rows), ok, len(rows), np.percentile(lat, 50), np.percentile(lat, 90), np.percentile(thr, 50)))
    if mock:
        print('  [mock] 数值为模拟值，仅验证统计/CSV 逻辑')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bit')
    ap.add_argument('--dma', default='axi_dma_0')
    ap.add_argument('--n', type=int, default=4096)
    ap.add_argument('--dtype', default='uint32')
    ap.add_argument('--repeat', type=int, default=100)
    ap.add_argument('--csv', default='dma_validate.csv')
    ap.add_argument('--mock', action='store_true')
    args = ap.parse_args()
    if args.mock:
        return run_mock(args)
    if not args.bit:
        ap.error('需要 --bit（板端）或 --mock')
    return run_board(args)


if __name__ == '__main__':
    sys.exit(main())
