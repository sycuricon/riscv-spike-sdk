# KVM 集成改动记录

本文保留实验推进顺序，并说明各阶段与当前实现的区别。当前可执行步骤详见 [KVM 操作指南](kvm-guide.md) 和 [Debian guest 指南](debian-guest.md)。

## 一、项目目录

```text
riscv-spike-sdk/
├── repo/                 # 组件源码
├── conf/
│   ├── linux_defconfig   # 当前 KVM 内核配置
│   ├── buildroot_base_defconfig # 当前基础 rootfs 构建配置
│   ├── rootfs-overlay/  # 加入基础 rootfs 的文件，如 etc/inittab
│   └── kvm/             # 原 A1 的 Buildroot 配置和 inittab 记录
├── scripts/              # 构建辅助、打包、启动脚本
├── docs/                 # 使用说明、版本和验证记录
├── build/                # 编译产物与暂存文件，Git 忽略
├── images/
│   ├── base/            # 构建生成的基础 rootfs
│   ├── kvm/             # OpenSBI 固件和外层 rootfs
│   └── debian/          # Debian 下载镜像、校验清单和可写 raw 磁盘
├── rootfs/               # 根文件系统构建输出，Git 忽略
├── Makefile              # 统一操作入口
└── README.md             # 项目总体说明
```

## 二、目录整理与 KVM 构建集成

### 1. 迁移基线配置

把 `baseline-a1` 配置文件挪到 `conf/kvm` 中。

当时的基线打包脚本从自己旁边读取 `inittab`，移动后需要同步修改路径。该旧脚本后来已移除；当前通过 `conf/rootfs-overlay/etc/inittab` 向 Buildroot 安装初始化配置。

用基线 `linux.config` 的内容替换 `conf/linux_defconfig`，随后删除重复的配置文件。当前内核配置包含 `CONFIG_KVM=m`，KVM 编译为独立模块。

### 2. 整理源码并注册子模块

把它们移入 `repo/` 并注册成子模块：

| 原目录 | 类型 | 整理方式 |
| --- | --- | --- |
| `work/kvmtool/` | 独立 Git 源码仓库 | 纳入 `repo/kvmtool/`，作为子模块 |
| `work/dtc/` | 独立 Git 源码仓库 | 纳入 `repo/dtc/`，作为子模块 |

原 `work/linux-kvm/` 是使用 `repo/linux/` 源码生成的独立构建输出目录，不是另一份 Linux 源码。现在统一输出到 `build/linux/`。QEMU 使用已有的 `repo/riscv-gnu-toolchain/qemu/` 子模块，不使用额外解压的 `repo/qemu/`。

### 3. 启动外层 Linux

在实验服务器上启动外层 RISC-V Linux，也就是后面运行 KVM 和 lkvm 的系统。

### 4. 切换工具链

改用 SDK 使用的工具链：

```text
toolchain/bin/riscv64-unknown-linux-gnu-gcc
```

Linux、KVM 模块、libfdt、lkvm 和 OpenSBI 使用这套 RISC-V 交叉工具链。QEMU 使用服务器本机编译器构建。基础 rootfs 的 Buildroot 配置使用 Bootlin 外部工具链，与 SDK 工具链分开管理。

### 5. 统一 Linux 构建规则

调整现有 Linux 构建规则，目标保持统一：

| 项目 | 路径 |
| --- | --- |
| 源码 | `repo/linux/` |
| 配置 | `conf/linux_defconfig` |
| 输出 | `build/linux/` |
| 编译器 | `toolchain/bin/riscv64-unknown-linux-gnu-gcc` |

### 6. 增加完整内核构建入口

编译内核、模块，并将模块安装到暂存目录：

```sh
make linux-build
```

输出：

```text
build/linux/arch/riscv/boot/Image
build/kvm-modules/lib/modules/<内核版本>/
```

### 7. 重新编译 libfdt

用 SDK 工具链重新编译 libfdt。

libfdt 是处理设备树的库。lkvm 创建 RISC-V guest 时，需要它来生成描述 CPU、内存和设备的信息。它会链接进 RISC-V 版 lkvm，因此也必须编译为 RISC-V 代码。

### 8. 重新构建 lkvm

用 SDK 工具链重新构建静态版 lkvm。

`make kvmtool-build` 依赖 `libfdt-build`，输出 `repo/kvmtool/lkvm-static`。它在外层 RISC-V Linux 中运行，通过 `/dev/kvm` 创建和运行 guest，不能直接在 x86_64 服务器上执行。

### 9. 重新打包外层 rootfs

将新模块、新 lkvm、guest 镜像和启动脚本加入基础 rootfs。早期手工产物命名为 `rootfs-kvm.cpio.gz`，当前自动打包的输出统一为 `images/kvm/rootfs-kvm-new.cpio.gz`。

```text
images/base/rootfs.cpio.gz        基础文件系统
    ＋ build/kvm-modules/         新模块
    ＋ repo/kvmtool/lkvm-static   新 lkvm
    ＋ guest 内核和原始 rootfs
    ＋ run-guest、run-debian 启动脚本
                ↓
images/kvm/rootfs-kvm-new.cpio.gz 新外层文件系统
```

早期手工集成使用 `build/rootfs-extra/`。当前脚本每次创建 `build/rootfs-pack.XXXXXX/root/` 临时目录，将新增文件打包成 cpio.gz，再与基础归档拼接；内核依次解包。结束后临时目录自动删除，不再依赖 `rootfs-extra/`。

`/opt/guest/Image` 复用本次构建的内核，`/opt/guest/rootfs.cpio.gz` 使用基础 rootfs，避免将完整外层镜像递归放进 guest。

### 10. 增加自动打包脚本

添加 `scripts/pack-kvm-rootfs.sh`，并将 `run-guest` 和 `run-debian` 安装到外层 `/usr/bin/`。

### 11. 修改 Makefile

`rootfs-kvm` 依赖 `rootfs-base`、`linux-build`、`kvmtool-build`。各构建依赖完成后，才执行打包脚本；使用 `-j` 时独立依赖可以并行。

## 三、增加 Debian 发行版 guest

### 1. 准备 Debian 磁盘镜像

保留现有 guest，**另做一份 Debian 磁盘镜像**。

- 下载镜像和校验清单在 `images/debian`。
- 转换成 raw 格式，供后续磁盘传递和 lkvm 使用。保留原 qcow2 文件作为下载基线。

qcow2 支持压缩、快照等特性。raw 是直接表示磁盘内容的文件，里面仍包含分区表和文件系统。

使用 Debian 13 trixie 的 riscv64 nocloud 镜像。转换后的文件为 `images/debian/debian-guest.raw`，已验证磁盘的第 1 分区是 ext4 根分区，第 15 分区是 EFI 分区。分区位置需要按实际镜像确认。

### 2. 尝试启动

首次启动进入过 emergency mode：EFI 挂载缺少字符集支持，且 root 账号锁定。通过 `init=/bin/sh` 维护模式设置 root 密码、按实际 UUID 修正 `/etc/fstab`，并屏蔽本实验不需要的 EFI 自动挂载与首次交互向导后，正常启动并登录成功。后续正常启动不再携带 `init=/bin/sh`。

### 3. 增加外层启动入口

Makefile 新增 `run-debian-host`：在原来的基础上启动外层 Linux，并传入 Debian 磁盘。

QEMU 把 raw 文件作为外层 `/dev/vda`；lkvm 通过 `-d /dev/vda` 将整盘提供给 guest。Debian 用 `root=/dev/vda1 rw rootwait` 从第 1 分区启动，不再使用基础 initramfs 作为 guest 根文件系统。Debian 磁盘不打包进外层 initramfs，不应同时被外层挂载或被其他虚拟机写入。

### 4. 增加 Debian 启动脚本

新增 `scripts/run-debian.sh`：在外层启动 Debian；打包脚本会把它安装为 `/usr/bin/run-debian`。

### 5. 配置两层网络

最初未启用网络，无法运行 `apt install`。之后先让外层 Linux 联网，再让 lkvm 给 Debian 提供网络，现已验证 DNS、APT 索引下载、`hello` 安装及运行。

- 外层 QEMU：构建时启用 libslirp 用户态网络；系统缺少开发库时，QEMU 构建系统根据 `slirp.wrap` 获取固定版本源码。
- 修改 Makefile：`run-debian-host` 增加用户态网络和 virtio 网卡；启动时自动使用项目里的 libslirp，不必再手动设置 `LD_LIBRARY_PATH`。
- 内层 Debian：通过 DHCP 获取地址、路由和 DNS，使用 systemd-networkd 与 systemd-resolved。
- `run-debian.sh` 在启动 lkvm 前执行外层 DHCP，并使用 `-n mode=user`。外层 rootfs 在内存中，每次重启后需重新配置网络。

```text
服务器网络
    ↓ QEMU 用户态网络
外层 Linux
    ↓ lkvm 用户态网络
Debian guest
```

曾为排查大文件超时，将 kvmtool 的 `UIP_MAX_TCP_PAYLOAD` 限制为 1024 字节。随后原版也完成约 9 MB 文件下载，不能认定该补丁必需，因此已撤销修改及自动补丁流程。当前使用原版 kvmtool；仍观察到 GRO 警告，长期网络稳定性尚未完成验证。

## 四、补充基础构建过程

早期仅复用同学提供的固件和基础 rootfs，后续补齐了从源码生成的过程。

当前已让这两个文件从源码生成，替代原来的预构建输入：

```text
images/base/rootfs.cpio.gz
images/kvm/fw_jump.bin
```

### 1. OpenSBI 固件

```text
repo/opensbi/
    ↓ 编译
build/opensbi/platform/generic/firmware/fw_jump.bin
    ↓ 安装
images/kvm/fw_jump.bin
```

在 Makefile 中增加 `opensbi-build`。

使用 SDK 交叉工具链、`PLATFORM=generic`、`FW_TEXT_START=0x80000000`、`FW_JUMP_ADDR=0x80200000`。已验证新固件启动外层 Linux、加载 KVM 并启动 Buildroot guest。

### 2. 基础 rootfs

```text
repo/buildroot/ ＋ conf/buildroot_base_defconfig ＋ conf/rootfs-overlay/
    ↓ 构建用户空间并打包
rootfs/buildroot_initramfs/images/rootfs.cpio.gz
    ↓ 安装
images/base/rootfs.cpio.gz
```

让新 rootfs 启动时自动挂载 `/dev`：

`rootfs-overlay` 保存需要覆盖 Buildroot 默认内容的文件。它的 `etc/inittab` 最终会成为虚拟机里的 `/etc/inittab`。

在 Makefile 中增加 `rootfs-base`。

配置启用 gzip 压缩的 cpio 输出。Buildroot 使用 Bootlin 外部工具链，输出目录为 `rootfs/buildroot_initramfs/`；其中 `target/` 是用户空间文件树，`images/rootfs.cpio.gz` 是正式镜像产物。应使用正式镜像，不直接将 `target/` 当作可部署根文件系统。

已验证新基础 rootfs 的登录、devtmpfs 挂载、设备节点、DHCP 和 HTTP 访问，并验证集成后的 Debian 启动与 DNS。完整的全新工作区重建测试仍未完成。

## 五、当前构建与启动顺序

源码子模块及系统构建依赖准备好后，在 Ubuntu 项目根目录执行：

```sh
make -j4 "$PWD/toolchain/bin/riscv64-unknown-linux-gnu-gcc"
make -j4 qemu-build
make -j4 opensbi-build
make -j4 rootfs-kvm
```

`rootfs-kvm` 会自动构建基础 rootfs，但不构建 QEMU、OpenSBI，也不准备 Debian 磁盘。`run-kvm-host` 仅确保 QEMU 目标存在并检查镜像，启动前仍需完成镜像构建。直接执行 `make` 的默认目标仍是 `all → vmlinux`，不是完整构建入口。

| guest | Ubuntu 上执行 | 登录外层 root 后执行 |
| --- | --- | --- |
| Buildroot | `make run-kvm-host` | `run-guest` |
| Debian | `make run-debian-host` | `run-debian` |

Buildroot guest 使用 1 个 vCPU、256 MiB 内存，默认不联网；Debian guest 使用 1 个 vCPU、768 MiB 内存及用户态网络。外层 QEMU 分配 2 GiB 内存，使用 TCG 模拟 RISC-V 并启用 H 扩展。

在 guest 内执行 `poweroff` 正常关机，回到外层后按 Ctrl+A 再按 X 退出 QEMU。Debian 的修改保存在 raw 磁盘中；外层与 Buildroot guest 的内存 rootfs 修改不会自动保存回镜像。

源码版本由子模块固定，配置、脚本和文档提交 Git；`build/`、`rootfs/`、`toolchain/`、`images/` 为构建输出或镜像输入，不提交。原始基线校验值仅作历史记录，不能校验每次重建的产物。本实验尚未实现 Virt 保护。
