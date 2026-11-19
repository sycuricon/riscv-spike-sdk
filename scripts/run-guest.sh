#!/bin/sh
set -eu
EXTRA=""
case "${1:-}" in
    "") ;;
    --regression) EXTRA="sdk_regression=guest" ;;
    *) echo 'Usage: run-guest [--regression]' >&2; exit 1 ;;
esac
test -c /dev/kvm || modprobe kvm
test -c /dev/kvm
exec /usr/bin/lkvm run --name sdk-guest -k /opt/guest/Image \
    -i /opt/guest/rootfs.cpio.gz -m 256 -c 1 --console serial -n mode=none \
    -p "console=ttyS0 earlycon=sbi rdinit=/sbin/init maxcpus=1 $EXTRA"
