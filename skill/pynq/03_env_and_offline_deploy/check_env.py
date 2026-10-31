# -*- coding: utf-8 -*-
"""PYNQ 环境自查脚本（板端/PC 通用，缺失项给 WARN/FAIL）

用法：
    python check_env.py            # 板端运行
    python check_env.py --json     # 输出 JSON 便于归档
退出码：0 无 FAIL；1 存在 FAIL
"""
import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys

results = []


def item(name, status, detail=''):
    results.append({'item': name, 'status': status, 'detail': detail})
    print('[%-4s] %-28s %s' % (status, name, detail))


def check():
    # 1) PYNQ
    try:
        import pynq
        ver = getattr(pynq, '__version__', 'unknown')
        item('pynq import', 'PASS', 'version=%s' % ver)
        try:
            from pynq import Device
            dev = Device.active_device
            item('pynq device', 'PASS', str(dev))
        except Exception as e:
            item('pynq device', 'WARN', 'cannot query: %s' % e)
    except ImportError:
        item('pynq import', 'WARN', 'not a PYNQ environment (PC 上属正常)')

    # 2) 系统
    item('platform', 'PASS', '%s %s' % (platform.system(), platform.machine()))
    try:
        kv = platform.uname().release
        item('kernel', 'PASS', kv)
    except Exception:
        item('kernel', 'WARN', '')
    if platform.machine() not in ('aarch64', 'armv7l'):
        item('architecture', 'WARN', '非 ARM 板卡架构（PC 上属正常）')
    else:
        item('architecture', 'PASS', platform.machine())

    # 3) 内存 / 磁盘
    try:
        mem_gb = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / (1024 ** 3)
        item('memory', 'PASS' if mem_gb >= 0.4 else 'WARN', '%.2f GB' % mem_gb)
    except Exception:
        item('memory', 'WARN', 'cannot query')
    try:
        du = shutil.disk_usage('/')
        free_gb = du.free / (1024 ** 3)
        item('disk free', 'PASS' if free_gb >= 2 else 'WARN', '%.1f GB' % free_gb)
    except Exception:
        item('disk free', 'WARN', 'cannot query')

    # 4) overlay 目录
    for d in ('/home/xilinx/overlays', '/home/xilinx/jupyter_notebooks'):
        if os.path.isdir(d):
            item('dir ' + d, 'PASS', '')
        else:
            item('dir ' + d, 'WARN', 'not found (可在 PYNQ 中自建)')

    # 5) /dev/mem
    if os.path.exists('/dev/mem'):
        item('/dev/mem', 'PASS' if os.access('/dev/mem', os.R_OK) else 'FAIL', '')
    else:
        item('/dev/mem', 'WARN', 'not found (PC 上属正常)')

    # 6) Jupyter
    try:
        out = subprocess.run(['systemctl', 'is-active', 'jupyter'], capture_output=True, text=True, timeout=3)
        item('jupyter service', 'PASS' if out.stdout.strip() == 'active' else 'WARN', out.stdout.strip())
    except Exception:
        item('jupyter service', 'WARN', 'cannot query')

    # 7) 网络
    try:
        ip = socket.gethostbyname(socket.gethostname())
        item('network ip', 'PASS' if not ip.startswith('127.') else 'WARN', ip)
    except Exception:
        item('network ip', 'WARN', 'cannot resolve')
    try:
        s = socket.create_connection(('8.8.8.8', 53), timeout=2)
        s.close()
        item('internet', 'PASS', 'online')
    except Exception:
        item('internet', 'WARN', 'offline (需离线安装依赖)')

    # 8) 依赖包
    for mod in ('numpy', 'PIL'):
        try:
            m = __import__(mod)
            item('module ' + mod, 'PASS', getattr(m, '__version__', 'unknown'))
        except ImportError:
            item('module ' + mod, 'FAIL', 'pip install ' + mod)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', action='store_true', help='输出 JSON 汇总')
    args = ap.parse_args()
    print('PYNQ environment self-check')
    print('-' * 60)
    check()
    fails = [r for r in results if r['status'] == 'FAIL']
    print('-' * 60)
    print('SUMMARY: %d checks, %d FAIL, %d WARN'
          % (len(results), len(fails), len([r for r in results if r['status'] == 'WARN'])))
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    print('PASS: env ok' if not fails else 'FAIL: see items above')
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
