# QEMU 用户态网络构建

在项目根目录执行：

```sh
make -j4 qemu-build
make run-debian-host
```

QEMU 配置显式启用 `--enable-slirp --enable-download`。若系统已有
可用的 libslirp 开发库，构建系统使用该库；否则 Meson 通过 QEMU
源码内的 `subprojects/slirp.wrap` 获取固定提交的 libslirp 源码并构建。
当前 wrap 固定提交为 `26be815b86e8d49add8c9a8b320239b9594ff03d`。

不需要 sudo，也不再需要手动下载、解压 libslirp 的 deb 包或修改
`slirp.pc`。首次构建需要可访问对应依赖下载站点；Python 构建工具、
GLib 开发文件等 QEMU 本身的构建依赖仍需具备。

使用构建目录中的 QEMU 检查网络后端：

```sh
./build/kvm/qemu/qemu-system-riscv64 -netdev help
```

输出应包含 `user`。`make run-debian-host` 提供 QEMU 用户态网络及
virtio 网卡；外层执行 `run-debian` 后通过 DHCP 配置网络，再以
lkvm 的 `mode=user` 启动 Debian。

QEMU 源码位于上游子模块 `repo/qemu/`，输出保存在 `build/kvm/qemu/`。
`make qemu-build` 重新配置并增量构建，不安装到工具链目录，也不修改
Debian 磁盘。大文件下载曾在嵌套用户态网络中超时；磁盘快照启动检查
和无网络 guest 回归不能证明 APT 下载已经稳定。
