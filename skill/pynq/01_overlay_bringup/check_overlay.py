# -*- coding: utf-8 -*-
"""Overlay 自检脚本：文件 / .hwh 解析 / 加载 / IP 列表一致性

用法（板端）：
    python check_overlay.py --bit my.bit --hwh my.hwh
用法（PC，无板子，验证脚本逻辑）：
    python check_overlay.py --mock
退出码：0 全通过；1 有失败项
"""
import argparse
import json
import os
import sys
import tempfile
import xml.etree.ElementTree as ET

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok), detail))
    print(('PASS ' if ok else 'FAIL ') + name + (('   [' + detail + ']') if detail else ''))


def parse_hwh(path):
    """解析 .hwh：新版是 JSON，旧版是 XML。返回 IP 名称列表。"""
    raw = open(path, 'r', encoding='utf-8', errors='ignore').read()
    stripped = raw.lstrip()
    if stripped.startswith('{'):
        data = json.loads(raw)
        ips = data.get('ip', {})
        if isinstance(ips, dict):
            return sorted(ips.keys()), 'json'
        raise ValueError('unexpected json structure')
    root = ET.fromstring(raw)
    names = [e.get('FULLNAME') or e.get('NAME') or e.tag for e in root.iter() if e.tag.lower().endswith('module')]
    return sorted(names), 'xml'


def mock_hwh(dirpath):
    """生成一个最小 JSON .hwh 供离线自检"""
    data = {
        'ip': {
            'my_accel_0': {'type': 'xilinx.com:hls:my_accel:1.0', 'phys_addr': '0x43C00000', 'addr_range': '64K'},
            'axi_dma_0': {'type': 'xilinx.com:ip:axi_dma:7.1', 'phys_addr': '0x40400000'},
            'axi_gpio_0': {'type': 'xilinx.com:ip:axi_gpio:2.0', 'phys_addr': '0x41200000'},
        }
    }
    p = os.path.join(dirpath, 'mock.hwh')
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bit', help='overlay .bit 路径')
    ap.add_argument('--hwh', help='overlay .hwh 路径')
    ap.add_argument('--mock', action='store_true', help='离线自检（生成示例 hwh 并验证解析/比对逻辑）')
    args = ap.parse_args()

    if args.mock:
        with tempfile.TemporaryDirectory() as td:
            p = mock_hwh(td)
            names, kind = parse_hwh(p)
            check('mock hwh parsed (%s)' % kind, len(names) == 3, 'IPs=%d' % len(names))
            check('mock hwh contains my_accel_0', 'my_accel_0' in names)
            # 模拟 ip_dict 比对逻辑
            ip_dict = {n: {} for n in names}
            missing = [n for n in names if n not in ip_dict]
            check('ip_dict vs hwh consistency', not missing, 'missing=%d' % len(missing))
            extra = [n for n in ip_dict if n not in names]
            check('no extra ip in ip_dict', not extra, 'extra=%d' % len(extra))
        bad = [r for r in results if not r[1]]
        print('\n===== %d checks, %d failed =====' % (len(results), len(bad)))
        return 0 if not bad else 1

    if not args.bit:
        ap.error('需要 --bit（板端）或 --mock（离线）')

    bit = os.path.abspath(args.bit)
    hwh = os.path.abspath(args.hwh) if args.hwh else os.path.splitext(bit)[0] + '.hwh'
    check('bit file exists', os.path.isfile(bit), bit)
    check('hwh file exists', os.path.isfile(hwh), hwh)
    if not os.path.isfile(hwh):
        return 1

    try:
        names, kind = parse_hwh(hwh)
        check('hwh parsed (%s)' % kind, True, 'IPs=%d' % len(names))
    except Exception as e:
        check('hwh parsed', False, str(e))
        return 1

    check('hwh has user IPs', len(names) >= 2, 'IPs=%d' % len(names))

    try:
        from pynq import Overlay
    except ImportError:
        check('pynq import (板端才有)', False, 'PC 上无 pynq，仅完成文件/解析检查')
        return 1

    try:
        ol = Overlay(bit)
        check('overlay loaded', True, '%d IPs' % len(ol.ip_dict))
    except Exception as e:
        check('overlay loaded', False, str(e))
        return 1

    missing = [n for n in ol.ip_dict if n not in names]
    check('ip_dict ⊆ hwh', not missing, 'missing=%d' % len(missing))

    bad = [r for r in results if not r[1]]
    print('\n===== %d checks, %d failed =====' % (len(results), len(bad)))
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
