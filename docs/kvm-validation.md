# Upstream KVM validation — 2026-11-17

Built and tested in the independent server checkout
`/home/czy/work/riscv-spike-sdk-upstream-sdk`, branch `sdk-kvm-upstream`.
The research checkout and its outputs were preserved.

| Component | Upstream commit |
| --- | --- |
| Linux 6.17.2 | `449d48b1b99fdaa076166e200132705ac2bee711` |
| QEMU 10.1.0 | `f8b2f64e2336a28bf0d50b6ef8a7d8c013e9bcf3` |
| OpenSBI 1.7 | `a32a91069119e7a5aa31e6bc51d5e00860be3d80` |
| dtc | `f99e3af0ecb67a9085478a9b8ddbcc25aa64931d` |
| kvmtool | `eb915c763e4b95dd4a9d32763fd449459742e053` |

Linux, OpenSBI, QEMU, libfdt and static lkvm were compiled in this checkout's
`build/kvm/`; no research kernel, firmware or QEMU binary was reused. Compilation
used the existing external RISC-V Linux toolchain and base Buildroot initramfs:

```sh
export CROSS_COMPILE=/home/czy/work/riscv-spike-sdk/rootfs/buildroot_initramfs/host/bin/riscv64-linux-
export BASE_ROOTFS=/home/czy/work/my_core_files/rootfs-devtmpfs.cpio.gz
make kvm-build KVM_JOBS=8
make kvm-verify
make kvm-test-static
make kvm-test
make kvm-test-debian DEBIAN_DISK=/home/czy/work/riscv-spike-sdk-submodules/images/debian/debian-guest.raw
```

Results:

- Component build and artifact/source verification: PASS.
- Static checks: 2/2 PASS (manifest tampering/missing outputs and ordered serial results).
- Ordinary host → diskless Buildroot guest → host: `KVM-REGRESSION ALL PASS`.
  Evidence: `build/kvm/logs/regression-20261117-143200-199137/`.
- Debian 13 snapshot smoke: PASS.
  Evidence: `build/kvm/logs/debian-smoke-20261117-143214/`.
  The guest booted with `init=/bin/sh`, checked Debian identity, RISC-V architecture,
  tmpfs write/read and command execution, powered off, and returned to the host.
  QEMU `snapshot=on` prevented writes to the original initialized raw disk.

The console and result files retain the pre-commit SDK HEAD/worktree status.
Their source pins and manifest identify the tested upstream components; that
pre-commit HEAD does not imply the research binaries were used.

Limitations: the existing cross compiler and base user space were inputs, so this
is not a clean-machine rebuild of those inputs. Normal Debian systemd login,
DHCP/DNS/apt throughput, SMP/stress, physical hardware and legacy Spike startup
were not tested here. The snapshot smoke does not resolve the previously observed
nested-network TX timeout. This branch implements ordinary KVM integration.
