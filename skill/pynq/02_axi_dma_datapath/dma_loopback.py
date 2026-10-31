# -*- coding: utf-8 -*-
"""AXI-DMA 回环模板（PYNQ）：图案 -> DMA -> 校验 -> 吞吐

用法（板端）：
    python dma_loopback.py --bit my.bit --dma axi_dma_0 --n 4096
用法（PC，验证脚本逻辑）：
    python dma_loopback.py --mock
"""
import argparse
import sys
import time

import numpy as np


def make_pattern(n, dtype=np.uint32, seed=0):
    rng = np.random.default_rng(seed)
    if np.issubdtype(dtype, np.integer):
        info = np.iinfo(dtype)
        return rng.integers(info.min, info.max, size=n, dtype=dtype)
    return rng.random(n).astype(dtype)


def sync_to_dev(buf):
    """兼容 PYNQ 2.6+ (sync_to_device) 与旧版 (flush)"""
    if hasattr(buf, 'sync_to_device'):
        buf.sync_to_device()
    elif hasattr(buf, 'flush'):
        buf.flush()
    else:
        raise RuntimeError('buffer has no sync_to_device/flush')


def sync_from_dev(buf):
    if hasattr(buf, 'sync_from_device'):
        buf.sync_from_device()
    elif hasattr(buf, 'invalidate'):
        buf.invalidate()
    else:
        raise RuntimeError('buffer has no sync_from_device/invalidate')


def dma_roundtrip_once(dma, src, dst, timeout=10.0):
    t0 = time.perf_counter()
    dma.sendchannel.transfer(src)
    dma.recvchannel.transfer(dst)
    dma.sendchannel.wait()
    dma.recvchannel.wait()
    return time.perf_counter() - t0


def run_board(bit, dma_name, n, dtype_str, repeat):
    from pynq import Overlay, allocate
    ol = Overlay(bit)
    dma = getattr(ol, dma_name)
    dtype = np.dtype(dtype_str)
    src = allocate(shape=(n,), dtype=dtype)
    dst = allocate(shape=(n,), dtype=dtype)

    pattern = make_pattern(n, dtype)
    ok = 0
    times = []
    for i in range(repeat):
        src[:] = pattern
        sync_to_dev(src)
        dt = dma_roundtrip_once(dma, src, dst)
        sync_from_dev(dst)
        same = bool(np.array_equal(np.asarray(dst), pattern))
        times.append(dt)
        if same:
            ok += 1
        else:
            print('  iter %d: MISMATCH (first diff at %s)' % (i, np.argmax(np.asarray(dst) != pattern)))

    nbytes = n * dtype.itemsize
    med = float(np.median(times))
    thr = nbytes / med / 1e6 if med > 0 else 0.0
    print('DMA %s: bytes=%d  repeat=%d  ok=%d/%d' % (dma_name, nbytes, repeat, ok, repeat))
    print('latency median %.3f ms  ->  throughput %.1f MB/s' % (med * 1e3, thr))
    print('PASS' if ok == repeat else 'FAIL')
    return 0 if ok == repeat else 1


def run_mock(n, repeat):
    """无板子：模拟 DMA 行为验证图案/校验/统计逻辑"""
    print('[mock] 模拟 DMA 回环（无 pynq），验证校验与统计逻辑')
    pattern = make_pattern(n)
    dst = pattern.copy()          # 模拟正确传输
    same = bool(np.array_equal(dst, pattern))
    times = [0.0005 + 0.00001 * i for i in range(repeat)]
    nbytes = n * pattern.dtype.itemsize
    thr = nbytes / float(np.median(times)) / 1e6
    print('DMA mock: bytes=%d repeat=%d same=%s' % (nbytes, repeat, same))
    print('latency median %.3f ms -> throughput %.1f MB/s' % (np.median(times) * 1e3, thr))
    # 故意制造一次错误，验证能检出
    bad = pattern.copy(); bad[0] = bad[0] + 1 if pattern.dtype.kind in 'iu' else bad[0] + 0.5
    print('mismatch detection:', 'OK' if not np.array_equal(bad, pattern) else 'BROKEN')
    print('PASS' if same and not np.array_equal(bad, pattern) else 'FAIL')
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bit')
    ap.add_argument('--dma', default='axi_dma_0')
    ap.add_argument('--n', type=int, default=4096, help='元素个数')
    ap.add_argument('--dtype', default='uint32', help='uint32/int32/uint16/float32')
    ap.add_argument('--repeat', type=int, default=1)
    ap.add_argument('--mock', action='store_true')
    args = ap.parse_args()
    if args.mock:
        return run_mock(args.n, max(args.repeat, 5))
    if not args.bit:
        ap.error('需要 --bit（板端）或 --mock')
    return run_board(args.bit, args.dma, args.n, args.dtype, max(args.repeat, 1))


if __name__ == '__main__':
    sys.exit(main())
