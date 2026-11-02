# board/scripts —— 板端运行脚本（包内相对路径）

所有脚本都以"包内相对路径"工作（不再硬编码作者机器路径）。

| 脚本 | 说明 |
|---|---|
| `selfcheck.ps1/.bat` | 环境/包/SD 卡自检 |
| `prepare_sd_card.ps1/.bat` | 写 SD 卡：BOOT.bin + 权重 zip + 编码后的测试集 |
| `prepare_images.ps1/.bat` | 只替换 SD 卡 `yolo_test/` |
| `read_serial.ps1/.bat` | 抓串口（等串口出现；开放提示复位；掉线自动重连；结束检查首帧是否截断） |
| `run_jtag.ps1/.bat` + `run_on_board.tcl` | JTAG 下载位流+ELF 并运行 |
| `render_results.ps1/.bat` + `render_from_serial.py` | 串口日志出图（记住/自动匹配/弹窗选择图片目录；支持 0001.png 等任意命名；跳过截断帧） |
| `encode_images.py` | 图片 → `img*.bin/img*.png/img_num.txt`（自然数值排序） |
| `decode_sd_outputs.py` + `decode_sd_outputs.bat` | 旧固件 out0/out1 文件解码出图 |
| `eval_serial_vs_gt.py` + `eval_serial_vs_gt.bat` | 串口日志 vs GT 命中率评测 |
| `check_jtag.tcl` | 只检查 JTAG 链路 |

依赖：
- Python 3.8+（`numpy`、`pillow`）——仅编码/出图/评测需要
- Vivado/SDK 2018.3 —— 仅 JTAG 路径需要
- Windows PowerShell 5.1

## 图片目录规则（2026-11-02 改进）

- `prepare_images.ps1` / `prepare_sd_card.ps1` 成功后会把**本次选择的原图目录**写入 `last_image_dir.txt`；
- `render_results.ps1` 找图片目录的顺序：
  1. 命令参数 `-ImageDir`（最优先）；
  2. `last_image_dir.txt` 里记住的目录（且图片数覆盖日志帧号）；
  3. `data/images_*` 中能覆盖日志帧号的目录；
  4. 以上都不满足时**弹出文件夹选择框**，让你手动选测试图片目录；
- 图片命名不要求 `img0.png`：`render_from_serial.py` 会按自然排序把日志第 N 帧对应到图片目录的第 N 张（支持 `0001.png`、`frame_1.png` 等），只要图片数量覆盖日志帧号即可。
