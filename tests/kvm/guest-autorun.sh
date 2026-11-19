#!/bin/sh
set -eu
case " $(cat /proc/cmdline) " in
    *' sdk_regression=guest '*) ;;
    *) exit 0 ;;
esac
fail() { echo 'KVM-REGRESSION FAIL guest'; poweroff; exit 1; }
test "$(uname -m)" = riscv64 || fail
memory=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)
test "$memory" -gt 131072 || fail
before=$(awk '{print int($1)}' /proc/uptime)
sleep 2
after=$(awk '{print int($1)}' /proc/uptime)
test "$after" -ge "$((before + 2))" || fail
echo 'KVM-REGRESSION GUEST PASS'
echo 'KVM-REGRESSION GUEST SHUTDOWN'
poweroff
