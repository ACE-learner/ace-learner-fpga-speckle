# 03 环境与离线部署（Environment & Offline Deploy）

## 适用范围
所有 PYNQ 板卡的环境自查、无网络环境装依赖、Jupyter 访问配置。与算法无关。

## 使用方法

### 步骤 1：板端环境自查
```bash
python check_env.py
```
输出并检查：
- PYNQ 版本、Linux 内核、板卡名（`pynq.Device`）
- 内存与 SD 卡剩余空间（>2 GB 才能装依赖）
- overlay 常用目录是否存在（`/home/xilinx/overlays`）
- `/dev/mem` 权限、Jupyter 服务状态、网络地址
- 结论：PASS/WARN/FAIL 清单，退出码 0 表示无 FAIL

### 步骤 2：离线安装依赖（板子常无外网）
1. 在 PC 上下载对应架构（aarch64）与 Python 版本的 wheel：
   ```bash
   pip download -d wheels/ --platform manylinux2014_aarch64 --only-binary=:all: numpy pillow pandas
   ```
2. 拷到板子（U 盘/SD/SCP 均可），板端安装：
   ```bash
   pip install --no-index --find-links wheels/ numpy pillow pandas
   ```
3. 用 `check_env.py` 复查版本。

### 步骤 3：Jupyter 访问
- PYNQ 镜像默认启动 Jupyter（`http://<板卡IP>:9090`，密码默认 `xilinx`）；
- 静态 IP：改 `/etc/network/interfaces` 或 `nmtui`；连不上时先用串口确认 IP；
- 修改密码：`jupyter notebook password`。

### 步骤 4：常见版本适配
| 项 | 说明 |
|---|---|
| PYNQ 2.5/2.6/2.7/3.x | Buffer API 不同（`flush/invalidate` vs `sync_*`）；overlay 目录结构略有差异 |
| 镜像与板卡 | PYNQ-Z1/Z2、ZCU104、Kria 镜像互不通用，必须对应板卡 |
| Python 版本 | 镜像自带 Python 3.6~3.10，装 wheel 时注意对应标签（cp36/cp310、aarch64） |

## 已验证效果
- 离线（PC）：`check_env.py` 在非 PYNQ 环境可运行，会正确报告"缺少 pynq/非 Zynq 平台"的 WARN/FAIL（本包已实测）。
- 上板：应输出 `PASS: env ok (pynq 2.x, board PYNQ-Z2, free >= 2GB)` 并退出码 0。

## 失效条件
- 非 PYNQ 镜像（纯 PetaLinux/裸机）上运行：脚本会报告 FAIL，属预期；
- 板子无网络且没有离线 wheel：依赖装不上，需先在 PC 下载。
