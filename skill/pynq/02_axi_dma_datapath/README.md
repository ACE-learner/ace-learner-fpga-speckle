# 02 AXI-DMA 数据通路（DMA Datapath）

## 适用范围
PS 内存 ↔ PL 加速器之间需要批量搬运数据的题目（图像/矩阵/张量）。与具体算法无关，只要 PL 侧有 AXI-Stream 或 AXI 主口。

## 使用方法

### 步骤 1：Vivado 侧确认
- 有 AXI DMA（或 AXI-Stream 直连 HP 口）；
- DMA 的 s2mm/mm2s 流方向正确（PS→PL 用 mm2s，PL→PS 用 s2mm）；
- 时钟/复位共用 `proc_sys_reset`；
- 记录 DMA IP 名称（脚本默认 `axi_dma_0`）与最大位宽。

### 步骤 2：板端跑回环模板
```bash
python dma_loopback.py --bit /home/xilinx/overlays/my.bit --dma axi_dma_0 --n 4096
```
流程：`pynq.allocate` 分配连续内存 → 填充已知图案 → `sync_to_device` → 启动 mm2s/s2mm → 等待 → `sync_from_device` → 用 `numpy.array_equal` 校验 → 计算吞吐。
PYNQ 版本差异（`sync_to_device` vs 旧版 `flush`）脚本已做兼容。

### 步骤 3：稳定性自检
```bash
python validate_dma.py --bit my.bit --dma axi_dma_0 --n 4096 --repeat 100
```
- 连续 100 次传输全一致 → PASS；
- 输出 `dma_validate.csv`（每次耗时/吞吐/是否一致），可直接作为报告附件的原始数据。

无板子时：
```bash
python validate_dma.py --mock
```
用模拟 DMA 验证图案生成、校验、统计与 CSV 写出逻辑（本包已实测通过）。

## 已验证效果
- 离线（PC）：mock 模式跑 `validate_dma.py`，100 次一致性校验与 CSV 输出正常（本包已实测）。
- 上板：回环图案 100 次全一致，吞吐按板卡不同通常在几百 MB/s ~ 数 GB/s 量级；将实测值填进 README 的"实机验证记录"。

## 失效条件 / 常见坑
| 现象 | 原因 | 处理 |
|---|---|---|
| 传输超时/挂死 | DMA 中断未接、PL 未 ready、TLAST 未正确产生 | 先查 PL 的 tvalid/tlast；用轮询模式确认 |
| 数据错位/部分正确 | 缓冲区未对齐（DMA 通常要求 64B 对齐）、长度不是位宽整数倍 | `pynq.allocate` 天然对齐；检查 n 与 dtype |
| 每次结果不同 | 缓存一致性未处理（HP 口 vs cache） | 传输前后 `sync_to_device/sync_from_device`（旧版 `flush/invalidate`） |
| 吞吐远低于预期 | 单次数据太小（固定开销大）、未用大页连续内存 | 增大 n（≥1 MB/次）再测；对比不同 n |
| 第二次传输失败 | buffer 未释放/复用未重新 sync | 复用前重新写数据并 sync；或每次 allocate |
