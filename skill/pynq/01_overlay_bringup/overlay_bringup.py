# -*- coding: utf-8 -*-
"""Overlay 加载与寄存器读写模板（PYNQ）

用法：
    python overlay_bringup.py <overlay.bit>                 # 加载并打印 IP 列表
    python overlay_bringup.py <overlay.bit> --read 0x0      # 读第一个 IP 的寄存器
    python overlay_bringup.py <overlay.bit> --ip myip_0 --read 0x0
    python overlay_bringup.py --mock                        # 无板子时演示输出格式

说明：
- 需要 pynq 包（板端自带）；PC 上无 pynq 时只能用 --mock。
- .hwh 与 .bit 必须同目录、同前缀。
"""
import argparse
import os
import sys


def load_overlay(bit_path):
    from pynq import Overlay  # 延迟导入：PC 上无 pynq 也能看 --help
    return Overlay(bit_path)


def list_ips(ol):
    print('%-28s %-18s %s' % ('ip_name', 'type', 'address_range'))
    print('-' * 78)
    for name in sorted(ol.ip_dict.keys()):
        info = ol.ip_dict[name]
        addrs = info.get('phys_addr', info.get('addr', ''))
        rng = info.get('addr_range', '')
        typ = info.get('type', '')
        print('%-28s %-18s %s' % (name, typ, '%s (size %s)' % (addrs, rng)))
    print('-' * 78)
    print('total IPs: %d' % len(ol.ip_dict))


def read_reg(ol, ip_name, offset, count=1):
    ip = getattr(ol, ip_name)
    vals = [ip.read(offset + 4 * i) for i in range(count)]
    for i, v in enumerate(vals):
        print('  %s.read(0x%X) = 0x%08X (%d)' % (ip_name, offset + 4 * i, v, v))
    return vals


def mock_demo():
    print('[mock] 没有 pynq 环境，演示输出格式（真实运行请去掉 --mock）')
    fake = {
        'axi_gpio_0': {'type': 'xilinx.com:ip:axi_gpio:2.0', 'phys_addr': '0x41200000', 'addr_range': '0x10000'},
        'axi_dma_0': {'type': 'xilinx.com:ip:axi_dma:7.1', 'phys_addr': '0x40400000', 'addr_range': '0x10000'},
        'my_accel_0': {'type': 'xilinx.com:hls:my_accel:1.0', 'phys_addr': '0x43C00000', 'addr_range': '0x10000'},
    }

    class MockOL:
        ip_dict = fake

        def __getattr__(self, k):
            class Reg:
                def read(self, off):
                    return 0xDEADBEEF if off == 0 else 0
            return Reg()

    list_ips(MockOL())
    print('  --read 示例：')
    read_reg(MockOL(), 'my_accel_0', 0x0, 2)


def main():
    ap = argparse.ArgumentParser(description='PYNQ overlay bring-up template')
    ap.add_argument('bit', nargs='?', help='overlay .bit 路径（与 .hwh 同前缀）')
    ap.add_argument('--ip', default=None, help='要读寄存器的 IP 名（默认第一个非 PS 的 IP）')
    ap.add_argument('--read', default=None, help='寄存器偏移，如 0x0')
    ap.add_argument('--count', type=int, default=1, help='读取寄存器个数')
    ap.add_argument('--mock', action='store_true', help='无 pynq 时演示输出格式')
    args = ap.parse_args()

    if args.mock:
        mock_demo()
        return 0
    if not args.bit:
        ap.error('需要 overlay .bit 路径，或使用 --mock')

    bit = os.path.abspath(args.bit)
    hwh = os.path.splitext(bit)[0] + '.hwh'
    if not os.path.exists(bit):
        print('ERROR: bit not found: %s' % bit)
        return 2
    if not os.path.exists(hwh):
        print('WARN: hwh not found: %s（Overlay 可能失败）' % hwh)

    try:
        ol = load_overlay(bit)
    except ImportError:
        print('ERROR: pynq 未安装（请在板端运行，或用 --mock）')
        return 3
    except Exception as e:
        print('ERROR: overlay load failed: %s' % e)
        return 4

    list_ips(ol)

    if args.read is not None:
        ip_name = args.ip
        if ip_name is None:
            candidates = [k for k in sorted(ol.ip_dict) if 'processing_system' not in k.lower()]
            if not candidates:
                print('ERROR: overlay has no user IP')
                return 5
            ip_name = candidates[0]
        off = int(args.read, 0)
        print('read %s @ 0x%X x%d:' % (ip_name, off, args.count))
        read_reg(ol, ip_name, off, args.count)

    print('PASS: overlay loaded (%d IPs)' % len(ol.ip_dict))
    return 0


if __name__ == '__main__':
    sys.exit(main())
