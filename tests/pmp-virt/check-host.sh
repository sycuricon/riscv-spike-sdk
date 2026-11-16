#!/bin/sh
set -eu

case "$(uname -r)" in
    *-pmpvirt-kvm-host|*-pmpvirt-kvm-host+|*-pmpvirt-kvm-host-*) ;;
    *) echo 'Run this in the protected host, not the Ubuntu server or guest.' >&2; exit 1 ;;
esac

test -c /dev/kvm || { echo '/dev/kvm missing; check built-in KVM initialization.' >&2; exit 1; }
test -c /dev/pvtest || { echo '/dev/pvtest missing.' >&2; exit 1; }
log_file=$(mktemp)
trap 'rm -f "$log_file"' EXIT HUP INT TERM
dmesg > "$log_file"
for marker in 'PMP.Virt ACCESS SUMMARY: PASS 6/6' 'PMP.Virt seal acknowledged'; do
    grep -Fq "$marker" "$log_file" || { echo "Missing boot result: $marker" >&2; exit 1; }
done
for phase in 'before seal' 'after seal'; do
    guard_count=$(grep -Fc "PMP.Virt SBI GUARD PASS $phase " "$log_file" || true)
    test "$guard_count" -eq 9 || { echo "Incomplete SBI guard results: $phase ($guard_count/9)" >&2; exit 1; }
done
if grep -Eq 'PMP.Virt .*FAIL|PMP.Virt seal FATAL' "$log_file"; then
    echo 'A PMP.Virt boot test failed.' >&2
    exit 1
fi
/usr/bin/pv-user-test
/usr/bin/pv-syscall-api
echo 'VIRT-KVM HOST CHECK PASS: seal, HS 6/6, SBI guard 18/18, U/HS/U, syscall API, /dev/kvm'
