# 01 Overlay 导出与加载（Overlay Bring-up）

## 适用范围
任何"Vivado 自定义 IP + PYNQ"的题目：需要把位流装到 PL 上，并在 Python 里访问 IP 的 AXI-Lite 寄存器。
与具体算法无关，示例 IP 可用任意名字替换。

## 使用方法

### 步骤 1：Vivado 侧导出
1. Block Design 里加好 IP，连接 AXI-Lite（控制）与 AXI-HP/DMA（数据）；
2. 综合、实现、生成 bitstream；
3. 导出硬件：`File → Export → Export Hardware`（勾 Include bitstream），得到 `xxx.bit` + `xxx.hwh`；
4. 把两个文件放同一目录（文件名前缀保持一致），拷到板子（如 `/home/xilinx/overlays/`）。

### 步骤 2：板端加载与检查
```bash
python overlay_bringup.py /home/xilinx/overlays/my_design.bit
python overlay_bringup.py /home/xilinx/overlays/my_design.bit --read 0x0 4
```

脚本会：
- 调用 `pynq.Overlay(bit_path)` 加载；
- 打印 overlay 内所有 IP 名称与地址范围；
- 可选：读取指定 IP 的寄存器偏移（模板里默认读第一个 IP 的 0x0）。

### 步骤 3：自检（推荐放进提交材料）
```bash
python check_overlay.py --bit /home/xilinx/overlays/my_design.bit --hwh /home/xilinx/overlays/my_design.hwh
```
检查项：文件存在、`.hwh` 可解析（JSON/XML）、IP 数量、加载后 `ip_dict` 与 `.hwh` 一致性；全部通过退出码为 0。

无板子时可在 PC 上验证脚本本身：
```bash
python check_overlay.py --mock
```

## 已验证效果
- 离线（PC）：mock 模式可生成示例 `.hwh` 并完成解析、比对、PASS/FAIL 输出（本包已实测通过）。
- 上板：按上面命令运行后，应看到 `PASS: overlay loaded, N IPs, ip_dict matches .hwh` 并退出码 0。

## 失效条件 / 常见坑
| 现象 | 原因 | 处理 |
|---|---|---|
| `Overlay` 报 hwh 找不到 | 只拷了 .bit 没拷 .hwh，或文件名前缀不一致 | 两文件同名同目录 |
| 加载成功但 IP 列表为空 | Vivado 导出时未勾选 bitstream，或 hwh 是旧版 XML | 重新导出，用 JSON 版 hwh |
| 加载报器件不匹配 | 位流不是该板卡/该 PS 配置生成 | 用对应板卡的工程重新生成 |
| 寄存器读写全 0 或超时 | AXI-Lite 未连、地址偏移错、时钟/复位没接 | 在 Vivado Address Editor 核对地址，检查 proc_sys_reset |
