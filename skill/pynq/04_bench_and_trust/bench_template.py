# -*- coding: utf-8 -*-
"""板端性能测量模板：预热 + 多次 + 分位数 + CSV

用法（板端，测 overlay 内某 IP 的寄存器往返延迟为例）：
    python bench_template.py --bit my.bit --ip my_accel_0 --offset 0x10 --warmup 5 --repeat 50 --csv bench.csv
用法（板端，测纯 Python 函数——把 --func 指向你自己的模块）：
    python bench_template.py --func mymodule:run_inference --warmup 5 --repeat 30
用法（PC 离线验证逻辑）：
    python bench_template.py --mock
退出码：0 成功；1 参数/导入错误
"""
import argparse
import csv
import importlib
import statistics
import sys
import time

import numpy as np


def run_bench(fn, warmup, repeat):
    for _ in range(warmup):
        fn()
    times = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t0)
    return np.array(times)


def write_csv(path, times):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['iter', 'latency_ms'])
        for i, t in enumerate(times):
            w.writerow([i, round(t * 1e3, 5)])
    print('CSV written:', path)


def summarize(times):
    ms = times * 1e3
    p50, p90, p99 = np.percentile(ms, [50, 90, 99])
    print('n=%d  mean=%.3f ms  p50=%.3f  p90=%.3f  p99=%.3f  min=%.3f  max=%.3f'
          % (len(ms), ms.mean(), p50, p90, p99, ms.min(), ms.max()))
    print('throughput(p50) = %.2f FPS' % (1000.0 / p50 if p50 else 0))
    return p50


def run_mock(repeat, warmup):
    print('[mock] 无板子：验证预热/分位数/CSV 逻辑')
    # 模拟：首次慢 5 倍（预热后进入稳态）
    calls = {'n': 0}

    def fake():
        calls['n'] += 1
        if calls['n'] <= warmup:
            time.sleep(0.005)      # 模拟首次调用较慢
            return
        time.sleep(0.001 + 0.00002 * (calls['n'] % 5))   # 模拟稳态 1ms

    times = run_bench(fake, warmup, repeat)
    p50 = summarize(times)
    write_csv('bench_mock.csv', times)
    ok = len(times) == repeat and 0.8 < p50 < 5.0   # 计时器精度不同，放宽到同数量级
    print('mock self-check:', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bit')
    ap.add_argument('--ip')
    ap.add_argument('--offset', default='0x0')
    ap.add_argument('--func', help='module:function 形式，测 Python 函数')
    ap.add_argument('--warmup', type=int, default=5)
    ap.add_argument('--repeat', type=int, default=50)
    ap.add_argument('--csv', default='bench.csv')
    ap.add_argument('--mock', action='store_true')
    args = ap.parse_args()

    if args.mock:
        return run_mock(max(args.repeat, 10), args.warmup)

    if args.func:
        mod_name, fn_name = args.func.split(':')
        mod = importlib.import_module(mod_name)
        fn = getattr(mod, fn_name)
    elif args.bit and args.ip:
        from pynq import Overlay
        ol = Overlay(args.bit)
        ip = getattr(ol, args.ip)
        off = int(args.offset, 0)

        def fn():
            ip.read(off)
    else:
        ap.error('需要 --bit/--ip 或 --func，或 --mock')

    times = run_bench(fn, max(args.warmup, 0), max(args.repeat, 1))
    summarize(times)
    write_csv(args.csv, times)
    print('PASS: benchmark done')
    return 0


if __name__ == '__main__':
    sys.exit(main())
