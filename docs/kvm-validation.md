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

## Preflight and independent-directory rebuild — 2026-11-19

Added compiler, static-link, source-pin and base-rootfs preflight checks. Static
checks now pass 4/4, including rejection of bare-metal compilers and invalid
base-rootfs inputs. `make kvm-check` and `make kvm-verify` passed.

A separate checkout at `build/repro-check/checkout` rebuilt Linux, OpenSBI,
QEMU, dtc/libfdt and lkvm without copying the original build outputs. Sources
were prepared from local repositories at the pinned revisions. The compiler
and base initramfs above remained explicit external inputs; this does not
verify internet cloning or rebuilding those inputs on a clean machine.

Independent-directory results:

- Ordinary KVM regression: PASS, evidence under that checkout at
  `build/kvm/logs/regression-20261119-132837-796420/`.
- Debian snapshot smoke: PASS, evidence under that checkout at
  `build/kvm/logs/debian-smoke-20261119-132927/`.

The main checkout also passed both runtime checks:
`build/kvm/logs/regression-20261119-132241-097236/` and
`build/kvm/logs/debian-smoke-20261119-132339/`.
These checks ran with the pending preflight changes before their final commit;
result files record that worktree state. The Debian smoke scope and network
limitations described above still apply. Build outputs, disks and runtime
logs are local inputs/evidence and are not included in the Git branch.

## Upstream master merge validation — 2026-11-19

Merged upstream master `0242f0c06d0abd00e5c4b6029011c96f847880e5`
into the generic KVM branch based on `6fef8a2397c7a1d6a898c24637c52421fe86ec8a`.
The Makefile retains upstream's uppercase variables, separate Linux/newlib builds,
header installation and legacy Spike targets. Generic KVM targets use the new
variables; the optional base-rootfs build now uses `build/buildroot-base/`.
The legacy QEMU source path points to `repo/qemu` and keeps slirp enabled.

The KVM Linux/OpenSBI/QEMU/dtc/kvmtool gitlinks still match `conf/kvm/sources.json`.
Linux stays at 6.17.2 and OpenSBI at 1.7, both community sources. The legacy Linux
config comes from upstream master; the KVM build uses its independent fragment.
Buildroot, GNU toolchain, Spike and OpenOCD gitlinks take the upstream revisions.
The legacy external-toolchain header declaration is 6.17 to match the pinned
Linux headers; the pinned Buildroot supports this option and GCC 16.

Validation after conflict resolution:

- Static tests: 4/4 PASS.
- `make kvm-check` with the external compiler/base rootfs documented above: PASS.
- `make kvm-verify`: PASS; KVM build inputs, binaries and source pins are unchanged.
- Makefile command previews for KVM entry points, base rootfs and legacy `all`: PASS.
- Ordinary KVM runtime: PASS. Evidence:
  `build/kvm/logs/regression-20261119-220921-623572/`.
- Debian 13 snapshot smoke: PASS. Evidence:
  `build/kvm/logs/debian-smoke-20261119-220935/`.

These runtime checks reused the independently built generic KVM components in
this checkout; they did not rebuild them or use research kernel/firmware/QEMU
binaries. Evidence records the pre-merge HEAD and pending worktree state.
The compiler and base initramfs remain external inputs. The new Buildroot pin,
compiler/newlib and legacy Spike build/boot were not rebuilt or executed here;
command previews are not build/runtime evidence. The optional base-rootfs route
was not rebuilt. Debian used a temporary disk snapshot with `init=/bin/sh`,
without writes to the original disk; normal systemd login/network/apt were not
retested. This merge does not change the previously recorded scope limitations.
