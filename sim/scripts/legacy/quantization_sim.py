# -*- coding: utf-8 -*-
"""模拟板端 int16 定点推理，定位"类别塌缩"的根因，并验证修复方向
模拟对象（与 HLS conv IP 一致）：
  1) BN 折叠进卷积（conv+BN -> 单 conv）
  2) 权重按 ×512 量化成 int16（四舍五入/截断 两种）
  3) 每层激活（ReLU 后）按 ×512 量化成 int16，范围 ±64（ap_fixed<16,7>）
对比：
  A. fp32（PC 端）
  B. int16 + 截断（若板端实际实现是这么做的）
  C. int16 + 四舍五入
  D. int16 + 四舍五入 + 激活 scale 1024（等价更多小数位 / 更小整数位）
指标：36 类 per-class top1 的“唯一位置数”
"""
import os
import sys

import numpy as np
import torch
import torch.nn as nn
from PIL import Image

ROOT = r'D:\BaiduNetdiskDownload\AI_FOR_YOLOV4'
PROJ = os.path.join(ROOT, 'yolov4-tiny-pytorch-master(1)')
GD = r'D:\fpga_work\board_out'
NC, MASK = 36, [[3, 4, 5], [1, 2, 3]]

sys.path.insert(0, PROJ)
from nets.yolo import YoloBody
from nets.CSPdarknet53_tiny import BasicConv
from utils.utils import get_anchors
from utils.utils_bbox import DecodeBox

anchors, _ = get_anchors(os.path.join(PROJ, 'model_data', 'yolo_anchors.txt'))
bu = DecodeBox(anchors, NC, (416, 416), MASK)


def build_folded_model():
    net = YoloBody(MASK, NC, phi=0, pretrained=False)
    net.load_state_dict(torch.load(os.path.join(ROOT, 'work', 'logs_1019', 'best_epoch_weights.pth'), map_location='cpu'), strict=True)
    net.eval()
    n_fold = 0
    for m in net.modules():
        if isinstance(m, BasicConv):
            conv, bn, act = m.conv, m.bn, m.activation
            eps = 1e-5
            with torch.no_grad():
                gamma = bn.weight; beta = bn.bias
                mu = bn.running_mean; var = bn.running_var
                std = torch.sqrt(var + eps)
                Wf = conv.weight * (gamma / std).view(-1, 1, 1, 1)
                if conv.bias is not None:
                    bf = (conv.bias - mu) * gamma / std + beta
                else:
                    bf = (0 - mu) * gamma / std + beta
                conv.weight.copy_(Wf)
                conv.bias = nn.Parameter(bf)
                bn.weight.data = torch.ones_like(gamma)
                bn.bias.data = torch.zeros_like(beta)
                bn.running_mean.data = torch.zeros_like(mu)
                bn.running_var.data = torch.ones_like(var)
            n_fold += 1
    return net, n_fold


def quant_tensor(x, scale, mode, int_range):
    """把张量按 scale 量化成定点(模拟 int16)，clip 到 ±int_range"""
    y = x * scale
    if mode == 'trunc':
        y = torch.trunc(y)
    else:
        y = torch.round(y)
    y = torch.clamp(y, -int_range * scale, int_range * scale)
    return y / scale


def build_model(mode, scale, int_range):
    net, n = build_folded_model()
    if mode == 'none':
        print('  折叠 BN 的层数:', n, '（不量化）')
        return net
    handles = []
    for name, m in net.named_modules():
        if isinstance(m, nn.Conv2d):
            def hook(mod, inp, out, _s=scale, _m=mode, _r=int_range):
                return quant_tensor(out, _s, _m, _r)
            handles.append(m.register_forward_hook(hook))
    print('  折叠 BN 的层数: %d ，量化层数: %d (mode=%s, scale=%d, 范围±%d)'
          % (n, len(handles), mode, scale, int_range))
    return net


def quant_weights(net, scale, mode, int_range):
    with torch.no_grad():
        for m in net.modules():
            if isinstance(m, nn.Conv2d):
                m.weight.data = quant_tensor(m.weight.data, scale, mode, int_range)
                if m.bias is not None:
                    m.bias.data = quant_tensor(m.bias.data, scale, mode, max(int_range, 1))


def unique_count(net):
    counts = []
    net.eval()
    for i in range(54):
        im = Image.open(os.path.join(GD, f'img{i}.png'))
        iw, ih = im.size
        inp = torch.from_numpy(np.fromfile(os.path.join(GD, f'img{i}.bin'), dtype='<f4').copy().reshape(1, 3, 416, 416))
        with torch.no_grad():
            p0, p1 = net(inp)
            outs = bu.decode_box([p0, p1])
            pred = torch.cat(outs, 1)[0]
        obj = pred[:, 4]
        cls = pred[:, 5:5 + NC]
        score = (obj.unsqueeze(1) * cls).numpy()
        cxy = pred[:, :2].numpy()
        kp = []
        for c in range(NC):
            idx = int(score[:, c].argmax())
            if score[idx, c] >= 0.002:
                kp.append((c, cxy[idx, 0] * iw, cxy[idx, 1] * ih, float(score[idx, c])))
        # 去重 3px（高分优先）
        kp.sort(key=lambda t: -t[3])
        kept = []
        for item in kp:
            if any(np.hypot(item[1] - k[1], item[2] - k[2]) <= 3.0 for k in kept):
                continue
            kept.append(item)
        counts.append(len(kept))
    return np.array(counts)


def run(label, mode, scale=512, int_range=64):
    print('=== %s ===' % label)
    net = build_model(mode, scale, int_range)
    if mode != 'none':
        quant_weights(net, scale, mode, int_range)
    c = unique_count(net)
    print('  唯一位置数: 平均 %.1f（最小 %d / 最大 %d）' % (c.mean(), c.min(), c.max()))
    return c.mean()


if __name__ == '__main__':
    base = run('A. fp32（PC 端，折叠BN但不量化）', 'none')
    trunc = run('B. int16 + 截断 (scale=512, ±64)', 'trunc', 512, 64)
    rnd = run('C. int16 + 四舍五入 (scale=512, ±64)', 'round', 512, 64)
    rnd2 = run('D. int16 + 四舍五入 (scale=1024, ±64)', 'round', 1024, 64)
    print()
    print('=== 汇总（36 类唯一位置数，54 帧均值）===')
    print('A fp32            : %.1f' % base)
    print('B 截断 scale512   : %.1f' % trunc)
    print('C 四舍五入 512    : %.1f' % rnd)
    print('D 四舍五入 1024   : %.1f' % rnd2)
