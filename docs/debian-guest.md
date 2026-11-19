# Debian riscv64 guest

## 磁盘和下载来源

Debian 用户空间运行在内层 guest，外层仍为已验证的 Buildroot Linux。复用 SDK 编译的 guest Image，不使用发行版磁盘上的内核或 EFI 启动链。

官方下载入口：<https://cloud.debian.org/images/cloud/trixie/latest/>。
本实验下载 debian-13-nocloud-riscv64.qcow2，虚拟容量 3 GiB。
原始下载文件的 SHA-512 为：

```text
145d2c0ee30cf35bd1ea978aae0995b56977321a28e1b39df41949f6b8654b2b3f34034aeb82769be1a0977171fc3c430a5ad815570d6e9c3ede914429876706
```

latest 是变化入口，此校验值仅标识本实验保存的原始文件。新下载时以同一发布批次的 SHA512SUMS 核验并记录版本，不要将新旧清单混用。当前记录完成了校验和比对，未记录签名验证结果。

在 Ubuntu 项目根目录执行；若目标文件已存在，先备份，不要覆盖：

```sh
set -e
mkdir -p images/debian
curl -fL --retry 3 -o images/debian/debian-13-nocloud-riscv64.qcow2 https://cloud.debian.org/images/cloud/trixie/latest/debian-13-nocloud-riscv64.qcow2
curl -fL --retry 3 -o images/debian/SHA512SUMS https://cloud.debian.org/images/cloud/trixie/latest/SHA512SUMS
(cd images/debian && sha512sum --ignore-missing -c SHA512SUMS)
./build/kvm/qemu/qemu-img convert -p -f qcow2 -O raw images/debian/debian-13-nocloud-riscv64.qcow2 images/debian/debian-guest.raw
fdisk -l images/debian/debian-guest.raw
```

确认校验输出明确包含该 qcow2 文件的 OK。raw 镜像仍包含 GPT 分区表，不是单独的 ext4 分区。已验证镜像根分区为第 1 分区，EFI 为第 15 分区。其他镜像必须重新检查。磁盘文件不打包进外层 initramfs，也不提交 Git。

## 首次初始化：在 guest 内完成，无需服务器 sudo

先在 Ubuntu 上完成 [构建](kvm-guide.md)，再执行：

```sh
make run-debian-host
```

登录外层 Buildroot root，将磁盘直接交给 lkvm，不在外层挂载。首次用维护 shell 启动，以下命令在外层执行：

```sh
modprobe kvm
/usr/bin/lkvm run --name debian-test -k /opt/guest/Image -d /dev/vda -m 768 -c 1 --console serial -n mode=none -p "console=ttyS0 root=/dev/vda1 rw rootwait init=/bin/sh"
```

进入维护 shell 后，以下命令在 Debian 内逐条执行。shell 此时是 PID 1，不要输入 exit，否则可能导致内核 panic：

```sh
mount -t proc proc /proc
mount -o remount,rw /dev/vda1 /
cat /etc/os-release
cat /etc/fstab
blkid /dev/vda1
cp -an /etc/fstab /etc/fstab.before-kvm
```

若 /proc 已挂载，不必重复挂载。读取当前实际 UUID，不能照抄其他镜像：

```sh
ROOT_UUID=$(blkid -s UUID -o value /dev/vda1)
test -n "$ROOT_UUID" && printf 'UUID=%s / ext4 defaults,errors=remount-ro 0 1\n' "$ROOT_UUID" > /etc/fstab
cat /etc/fstab
passwd root
```

passwd 的密码由使用者交互设置，不写入源码、文档或日志。本实验原始fstab 的根 PARTUUID 无法匹配，且 EFI 挂载因缺少 iso8859-1 而失败。当前直接加载内核的实验无需 EFI 挂载；此 fstab 只保留根分区。

屏蔽首次交互向导与 EFI 自动挂载，设置会保存在 Debian 磁盘中：

```sh
mkdir -p /etc/systemd/system
ln -s /dev/null /etc/systemd/system/systemd-firstboot.service
ln -s /dev/null /etc/systemd/system/efi.mount
ln -s /dev/null /etc/systemd/system/efi.automount
sync
exec /sbin/init
```

若链接已存在，检查其指向；已指向 /dev/null 即已屏蔽，不需重复创建。初始化向导被关闭后，时区、主机名等可登录后按需要自行配置。

用 root 和刚设置的密码登录。检查：

```sh
findmnt /
systemctl --failed
poweroff
```

关闭 guest 后返回外层，执行 run-debian 即为正常启动，不再带 init=/bin/sh。上述初始化仍为手动步骤，并非仓库已经自动完成。

## 日常运行与网络

Ubuntu 项目根目录：

```sh
make kvm-build KVM_JOBS=4
make run-debian-host
```

外层 root shell：

```sh
run-debian
```

run-debian 自动执行外层 DHCP，使用 lkvm mode=user。通常外层 eth0 为 10.0.2.15，内层 enp0s0 为 192.168.33.15；以实际输出为准。外层 DNS 配置须在 lkvm 启动前准备好。

Debian 内先执行 date -u，与 Ubuntu 服务器的当前时间核对。维护 shell 不运行时间同步服务；如果 HTTPS 报证书尚未生效，先校正时间，不要关闭证书、APT 签名或有效期检查。网卡在维护 shell 中可能叫 eth0，正常启动后可能叫 enp0s0，以 ip -br link 为准。

Debian 内检查：

```sh
ip -br addr
ip route
resolvectl status
getent ahostsv4 deb.debian.org
apt-get update
apt-get install --no-install-recommends hello
hello
```

历史基线曾运行 hello；不能将该结果视为当前分支的联网验证。大文件下载在 lkvm 用户态网络中出现过 TX watchdog 和超时。apt-get update 是更新软件包目录，不是升级整套系统；它不是离线 KVM 启动回归的前置条件。当前验证范围见 [KVM 验证](kvm-validation.md)。

只需要安装二进制软件时，可备份到 /root 后将 debian.sources 中的Types: deb deb-src 改为 Types: deb，减少源码索引下载。不要关闭签名检查。本实验也使用过 Acquire::Languages=none 跳过翻译索引。

在 Debian 执行 poweroff 正常关闭 guest，返回外层后 Ctrl+A 再按 X 退出 QEMU。Debian 文件修改和安装的软件保存在 raw 磁盘中。

## 常见问题

- 磁盘 write lock：先用 fuser -v images/debian/debian-guest.raw 查占用者，
  回到原会话正常关机。不要让两个 QEMU 同时写同一磁盘，也不要绕过锁。
- EFI 挂载失败：确认当前使用直接内核启动，再按首次配置屏蔽两个 EFI 单元。
- DNS 不通：先确认外层 IP、路由和 /etc/resolv.conf；外层 rootfs 重启会重置。
- 串口粘贴混乱：每次一条短命令。当前 Bash 可执行
  `bind 'set enable-bracketed-paste off'`；需要持久设置时在 /root/.inputrc
  增加 `set enable-bracketed-paste off`。这不能解决网络查询本身的等待。
- QEMU 网络依赖失败：检查构建日志及系统 slirp 开发依赖，见 [QEMU 网络文档](qemu-network.md)。
