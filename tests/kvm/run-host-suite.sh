#!/bin/sh
set -eu
fail() { echo 'KVM-REGRESSION FAIL host'; exit 1; }
test "$(uname -m)" = riscv64 || fail
test -c /dev/kvm || modprobe kvm || fail
test -c /dev/kvm || fail
echo 'KVM-REGRESSION HOST BEFORE PASS'
/usr/bin/run-guest --regression || fail
echo 'KVM-REGRESSION GUEST RETURNED'
test -c /dev/kvm || fail
echo 'KVM-REGRESSION HOST AFTER PASS'
echo 'KVM-REGRESSION ALL PASS'
