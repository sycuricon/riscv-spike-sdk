# Upstream RISC-V KVM SDK

This branch keeps QEMU, Linux, OpenSBI, dtc and kvmtool at the upstream commits in
`conf/kvm/sources.json`. The source URLs are upstream URLs; the gitlinks pin exact
versions. There are no research patches or automatic floating branch updates.
The host runs Buildroot; the inner guest runs Buildroot or Debian 13.

## Dependencies and build

Use an x86-64 Linux build server with Git, Make, Python 3.10+, a C/C++ toolchain,
cpio, gzip, pkg-config, bison, flex, bc, OpenSSL/ELF development libraries and
QEMU's GLib/pixman/slirp development dependencies. QEMU may download its pinned
subprojects. A RISC-V Linux cross compiler is needed for the kernel/firmware/lkvm.

```sh
make kvm-prepare                       # initialize only the five KVM submodules
export CROSS_COMPILE=/path/to/riscv64-linux-
# Either build the base user space from the pinned Buildroot submodule:
git submodule update --init --depth=1 -- repo/buildroot
make rootfs-base
# Or supply an existing Buildroot base (with init, sh, mount, getty, modprobe,
# udhcpc and the standard /etc/init.d/rcS startup sequence):
export BASE_ROOTFS=/path/to/rootfs.cpio.gz
make kvm-build KVM_JOBS=4
make kvm-verify
make kvm-test-static
make kvm-test
```

The compiler is selected with CROSS_COMPILE; it is not rebuilt implicitly.
All KVM outputs are isolated in `build/kvm/`. Kernel modules use a matching
`-sdk-kvm` kernel release. Dtc and kvmtool build in private clones so the pinned
submodule working trees stay clean. Keep the submodule object stores available
until builds finish. No kernel, QEMU or firmware binary is borrowed from the
research branch. The manifest checks source pins, build inputs and output hashes.
The ordinary KVM kernel starts from the upstream RISC-V defconfig and applies
`conf/kvm/linux.fragment`, rather than enabling unrelated distribution drivers.

Individual targets: `linux-build`, `opensbi-build`, `qemu-build`, `kvmtool-build`
(also builds libfdt), and `kvm-pack`. After changing a build input, rebuild its
component and repack before verifying/running. `rootfs-kvm` builds Linux/lkvm and
packs the rootfs; a full `kvm-build` also builds firmware and QEMU.

## Run and stop

```sh
make run-kvm-host
# Login root on the outer Buildroot host, then:
run-guest
```

The inner guest uses one vCPU, 256 MiB and no networking. `poweroff` returns to
the outer host. Ctrl+A, release, then X exits the outer QEMU.

`make kvm-test` automatically logs into the host, loads KVM, starts the ordinary
guest, checks guest memory and time progression, shuts it down and checks host
return. Only the explicit `sdk_regression=guest` boot flag enables automatic
guest tests/shutdown. Results are saved in `build/kvm/logs/regression-*/` with
the console, manifest snapshot, SDK commit/status, result and SHA256SUMS.
This is an ordinary KVM smoke test, not a security or performance benchmark.

For Debian use `make run-debian-host DEBIAN_DISK=/absolute/path/to/debian-guest.raw`
and run `run-debian` in the outer host. See [Debian setup](debian-guest.md).
The disk remains independent of the initramfs; never share a writable disk
between running VMs. Network/apt tests are separate from the diskless regression.

For an automated Debian user-space smoke test:

```sh
make kvm-test-debian DEBIAN_DISK=/absolute/path/to/debian-guest.raw
```

This uses a temporary QEMU disk snapshot and `init=/bin/sh`, checks Debian 13,
RISC-V, file I/O and command execution, powers off the guest and checks host
return. It does not require a password or alter the original disk. It does not
test normal systemd login, network or apt. Evidence is under
`build/kvm/logs/debian-smoke-*/`.

## Validation

Current validation is recorded in [KVM validation](kvm-validation.md).
The original Spike targets remain present but have not been retested in this
KVM work. A clean-machine build including compiler and base user space is also
separate from a component build using an existing compiler/base initramfs.
