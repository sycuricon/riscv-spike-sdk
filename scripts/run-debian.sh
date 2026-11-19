#!/bin/sh
set -eu

# 在外层 Linux 中执行，磁盘需由 make run-debian-host 提供。
DISK="${1:-/dev/vda}"
if [ ! -b "$DISK" ]; then
    echo "Debian disk not found: $DISK" >&2
    exit 1
fi

# 外层 rootfs 在内存中，每次启动后都需要重新配置网络。
# 在 lkvm 启动前获取 IP、路由和 DNS，供其用户态网络使用。
NET_IFACE="${NET_IFACE:-eth0}"
if ! udhcpc -i "$NET_IFACE" -n -q -t 5 -T 3; then
    echo "Failed to configure host network: $NET_IFACE" >&2
    exit 1
fi

if [ ! -c /dev/kvm ]; then
    modprobe kvm
fi

# 不在外层挂载此磁盘；将整盘独占交给 Debian guest。
exec /usr/bin/lkvm run \
    --name debian-test \
    -k /opt/guest/Image \
    -d "$DISK" \
    -m 768 \
    -c 1 \
    --console serial \
    -n mode=user \
    -p "console=ttyS0 root=/dev/vda1 rw rootwait"
