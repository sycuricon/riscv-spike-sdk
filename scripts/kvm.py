#!/usr/bin/env python3
"""Build and run an upstream RISC-V KVM SDK in build/kvm/."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import platform

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "build/kvm"
SOURCES = json.loads((ROOT / "conf/kvm/sources.json").read_text())["sources"]
INPUTS = ("conf/kvm/sources.json", "conf/kvm/linux.fragment",
          "conf/rootfs-overlay/etc/inittab", "scripts/kvm.py",
          "scripts/run-guest.sh", "scripts/run-debian.sh",
          "tests/kvm/guest-autorun.sh", "tests/kvm/run-host-suite.sh")
OUTPUTS = ("linux/arch/riscv/boot/Image", "opensbi/platform/generic/firmware/fw_jump.bin",
           "qemu/qemu-system-riscv64", "src/kvmtool/lkvm-static",
           "images/rootfs-kvm.cpio.gz", "images/guest-rootfs.cpio.gz")


def run(args, **kwargs):
    args = list(map(str, args))
    print("+ " + shlex.join(args), flush=True)
    return subprocess.run(args, check=True, **kwargs)


def output(args, **kwargs):
    return subprocess.check_output(list(map(str, args)), text=True, **kwargs).strip()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def require_checkout():
    if Path(output(["git", "-C", ROOT, "rev-parse", "--show-toplevel"])).resolve() != ROOT:
        raise RuntimeError("Run from an SDK Git checkout")


def source(name):
    details = SOURCES[name]
    path = ROOT / details["path"]
    if not (path / ".git").exists():
        raise RuntimeError(f"Initialize {details['path']} with make kvm-prepare")
    revision = output(["git", "-C", path, "rev-parse", "HEAD"])
    index = output(["git", "-C", ROOT, "ls-files", "--stage", "--", details["path"]]).split()
    if revision != details["revision"] or index[:3] != ["160000", revision, "0"]:
        raise RuntimeError(f"Source/gitlink/lock mismatch: {name}")
    if output(["git", "-C", path, "status", "--porcelain", "--untracked-files=all"]):
        raise RuntimeError(f"Source has local edits; preserve them before building: {name}")
    return path


def prepare():
    for name, details in SOURCES.items():
        if not (ROOT / details["path"] / ".git").exists():
            run(["git", "-C", ROOT, "submodule", "update", "--init", "--depth=1", "--", details["path"]])
        source(name)


def private_source(name):
    original = source(name)
    target = WORK / "src" / name
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--shared", "--no-checkout", original, target])
        run(["git", "-C", target, "checkout", "--detach", SOURCES[name]["revision"]])
    if output(["git", "-C", target, "rev-parse", "HEAD"]) != SOURCES[name]["revision"]:
        raise RuntimeError(f"Private source revision mismatch: {target}")
    if output(["git", "-C", target, "status", "--porcelain", "--untracked-files=all"]):
        raise RuntimeError(f"Private source has edits: {target}")
    return target


def compiler():
    prefix = os.environ.get("CROSS_COMPILE", str(ROOT / "toolchain/bin/riscv64-unknown-linux-gnu-"))
    path = shutil.which(prefix + "gcc")
    if not path:
        raise RuntimeError("Set CROSS_COMPILE to a RISC-V Linux compiler prefix")
    prefix = str(Path(path).absolute())[:-3]
    target = output([prefix + "gcc", "-dumpmachine"])
    if not target.startswith("riscv64-") or "linux" not in target:
        raise RuntimeError("A RISC-V 64-bit Linux compiler is required (not a bare-metal compiler)")
    return prefix


def base_rootfs():
    base = Path(os.environ.get("BASE_ROOTFS", ROOT / "images/base/rootfs.cpio.gz")).expanduser().resolve()
    if not base.is_file():
        raise RuntimeError("Run make rootfs-base, or set BASE_ROOTFS to a base initramfs")
    return base


def validate_rootfs(base):
    with gzip.open(base, "rb") as stream:
        data = stream.read()
    listing = subprocess.run(["cpio", "-it", "--quiet"], input=data,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    names = {name.removeprefix("./") for name in listing.stdout.decode().splitlines()}
    required = {"sbin/init", "bin/sh", "bin/mount", "sbin/getty", "sbin/modprobe",
                "sbin/udhcpc", "sbin/poweroff", "etc/init.d/rcS", "etc/init.d/rcK",
                "bin/sleep", "bin/cat", "bin/uname", "bin/busybox"}
    missing = sorted(required - names)
    if not names.intersection({"bin/awk", "usr/bin/awk"}):
        missing.append("awk (bin/awk or usr/bin/awk)")
    if missing:
        raise RuntimeError("Base rootfs is missing required files/applets: " + ", ".join(missing))
    busybox = subprocess.run(["cpio", "-i", "--to-stdout", "--quiet", "bin/busybox", "./bin/busybox"],
                             input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout
    if busybox[:6] != b"\x7fELF\x02\x01" or int.from_bytes(busybox[18:20], "little") != 243:
        raise RuntimeError("Base BusyBox must be a little-endian RV64 ELF executable")
    print(f"Base rootfs files and RV64 BusyBox: PASS ({base})", flush=True)


def check():
    if sys.platform != "linux" or platform.machine() not in ("x86_64", "amd64"):
        raise RuntimeError("Use an x86-64 Linux build server")
    if sys.version_info < (3, 10):
        raise RuntimeError("Python 3.10 or newer is required")
    required = ("git", "make", "gcc", "g++", "cpio", "gzip", "pkg-config", "bison", "flex", "bc", "ninja")
    missing = [name for name in required if not shutil.which(name)]
    if missing:
        raise RuntimeError("Missing build commands: " + ", ".join(missing))
    run(["pkg-config", "--exists", "glib-2.0", "pixman-1", "openssl", "libelf"])
    cross = compiler()
    with tempfile.TemporaryDirectory(prefix="sdk-compiler-") as temporary:
        executable = Path(temporary) / "probe"
        run([cross + "gcc", "-static", "-x", "c", "-", "-o", executable],
            input=b"int main(void) { return 0; }\n")
        data = executable.read_bytes()
        if data[:6] != b"\x7fELF\x02\x01" or int.from_bytes(data[18:20], "little") != 243:
            raise RuntimeError("Compiler did not produce an RV64 Linux executable")
    for name in SOURCES:
        source(name)
    validate_rootfs(base_rootfs())
    print(f"KVM build preflight: PASS; compiler={cross}", flush=True)


def build_component(name, jobs):
    WORK.mkdir(parents=True, exist_ok=True)
    if name == "qemu":
        src = source(name)
        dest = WORK / "qemu"
        dest.mkdir(exist_ok=True)
        run([src / "configure", "--target-list=riscv64-softmmu", "--disable-docs",
             "--enable-slirp", "--enable-download"], cwd=dest)
        run(["make", f"-j{jobs}"], cwd=dest)
        return
    cross = compiler()
    if name == "linux":
        src = source(name)
        dest = WORK / "linux"
        dest.mkdir(exist_ok=True)
        args = ["make", "-C", src, f"O={dest}", "ARCH=riscv", f"CROSS_COMPILE={cross}"]
        run(args + ["defconfig"])
        run(["sh", src / "scripts/kconfig/merge_config.sh", "-m", "-O", dest,
             dest / ".config", ROOT / "conf/kvm/linux.fragment"], cwd=src)
        run(args + ["olddefconfig"])
        config = (dest / ".config").read_text().splitlines()
        for required in ("CONFIG_KVM=m", "CONFIG_VIRTIO_BLK=y", "CONFIG_VIRTIO_NET=y",
                         "CONFIG_EXT4_FS=y", "CONFIG_DEVTMPFS_MOUNT=y"):
            if required not in config:
                raise RuntimeError(f"Required kernel option missing: {required}")
        run(args + [f"-j{jobs}", "Image", "modules"])
        run(args + [f"INSTALL_MOD_PATH={WORK / 'modules'}", "modules_install"])
    elif name == "opensbi":
        run(["make", "-C", source(name), f"O={WORK / 'opensbi'}", "PLATFORM=generic",
             "PLATFORM_RISCV_XLEN=64", f"CROSS_COMPILE={cross}", "FW_TEXT_START=0x80000000",
             "FW_JUMP_ADDR=0x80200000", f"-j{jobs}"])
    elif name == "kvmtool":
        dtc = private_source("dtc")
        run(["make", "-C", dtc, f"CC={cross}gcc", f"AR={cross}ar", "NO_VALGRIND=1",
             "NO_YAML=1", f"-j{jobs}", "libfdt"])
        run(["make", "-C", private_source(name), "ARCH=riscv", f"CROSS_COMPILE={cross}",
             f"LIBFDT_DIR={dtc / 'libfdt'}", f"-j{jobs}", "lkvm-static"])
    else:
        raise RuntimeError(f"Unknown build component: {name}")


def install(src, dst, executable=False):
    dst.parent.mkdir(parents=True, exist_ok=True)
    data = Path(src).read_bytes()
    if executable and data.startswith(b"#!"):
        data = data.replace(b"\r\n", b"\n")
    dst.write_bytes(data)
    dst.chmod(0o755 if executable else 0o644)


def archive(base, overlays, destination):
    # Emit one cpio stream, so both Linux and BusyBox cpio see the overlay.
    with tempfile.TemporaryDirectory(dir=WORK, prefix="rootfs-") as temporary:
        stage = Path(temporary)
        with gzip.open(base, "rb") as stream:
            run(["cpio", "-idm", "--no-absolute-filenames"], cwd=stage,
                input=stream.read(), stdout=subprocess.DEVNULL)
        for src, relative, executable in overlays:
            install(src, stage / relative, executable)
        names = ["."] + ["./" + p.relative_to(stage).as_posix() for p in sorted(stage.rglob("*"))]
        result = subprocess.run(["cpio", "--null", "-o", "-H", "newc", "--owner=0:0"],
                                input=("\0".join(names) + "\0").encode(), cwd=stage,
                                stdout=subprocess.PIPE, check=True)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = destination.with_suffix(".tmp")
        with temporary_file.open("wb") as target:
            with gzip.GzipFile(fileobj=target, mode="wb", filename="", mtime=0) as compressed:
                compressed.write(result.stdout)
        temporary_file.replace(destination)


def pack():
    base = base_rootfs()
    validate_rootfs(base)
    WORK.mkdir(parents=True, exist_ok=True)
    guest = WORK / "images/guest-rootfs.cpio.gz"
    archive(base, [(ROOT / "tests/kvm/guest-autorun.sh", "etc/init.d/S99sdk-regression", True)], guest)
    overlays = [(ROOT / "conf/rootfs-overlay/etc/inittab", "etc/inittab", False),
                (WORK / "src/kvmtool/lkvm-static", "usr/bin/lkvm", True),
                (WORK / "linux/arch/riscv/boot/Image", "opt/guest/Image", False),
                (guest, "opt/guest/rootfs.cpio.gz", False),
                (ROOT / "scripts/run-guest.sh", "usr/bin/run-guest", True),
                (ROOT / "scripts/run-debian.sh", "usr/bin/run-debian", True),
                (ROOT / "tests/kvm/run-host-suite.sh", "usr/bin/test-kvm-all", True)]
    release = (WORK / "linux/include/config/kernel.release").read_text().strip()
    modules = WORK / "modules/lib/modules" / release
    if not (modules / "kernel/arch/riscv/kvm/kvm.ko").is_file():
        raise RuntimeError("KVM module is missing; run make linux-build")
    for path in modules.rglob("*"):
        if path.is_file() and not path.is_symlink():
            overlays.append((path, "lib/modules/" + release + "/" + path.relative_to(modules).as_posix(), False))
    archive(base, overlays, WORK / "images/rootfs-kvm.cpio.gz")
    paths = [ROOT / item for item in INPUTS] + [WORK / item for item in OUTPUTS]
    state = {"schema": 1, "sources": SOURCES, "base_rootfs": {"path": str(base), "sha256": digest(base)},
             "files": {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}}
    (WORK / "manifest.json").write_text(json.dumps(state, indent=2) + "\n")
    verify()


def verify():
    state = json.loads((WORK / "manifest.json").read_text())
    expected = set(INPUTS) | {"build/kvm/" + p for p in OUTPUTS}
    if state.get("schema") != 1 or state.get("sources") != SOURCES or set(state["files"]) != expected:
        raise RuntimeError("Manifest source or file list mismatch; rebuild/repack")
    for name in SOURCES:
        source(name)
    for name, checksum in state["files"].items():
        if digest(ROOT / name) != checksum:
            raise RuntimeError(f"Artifact/input checksum mismatch: {name}; rebuild/repack")
    print("KVM artifact hashes and pinned sources: PASS", flush=True)


def launch(dry_run=False):
    verify()
    args = [WORK / "qemu/qemu-system-riscv64", "-machine", "virt", "-accel", "tcg",
            "-cpu", "rv64,h=true", "-m", "2048M", "-smp", "1", "-nographic",
            "-bios", WORK / "opensbi/platform/generic/firmware/fw_jump.bin",
            "-kernel", WORK / "linux/arch/riscv/boot/Image",
            "-initrd", WORK / "images/rootfs-kvm.cpio.gz",
            "-append", "console=ttyS0 earlycon=sbi rdinit=/sbin/init maxcpus=1"]
    if os.environ.get("DEBIAN_DISK"):
        disk = Path(os.environ["DEBIAN_DISK"]).expanduser().resolve()
        if not disk.is_file() or not os.access(disk, os.R_OK | os.W_OK):
            raise RuntimeError(f"Debian disk must be readable/writable: {disk}")
        args += ["-drive", f"file={str(disk).replace(',', ',,')},format=raw,if=none,id=debian",
                 "-device", "virtio-blk-device,drive=debian", "-netdev", "user,id=hostnet",
                 "-device", "virtio-net-device,netdev=hostnet"]
    print(shlex.join(list(map(str, args))), flush=True)
    if not dry_run:
        os.execv(str(args[0]), list(map(str, args)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "check", "build", "linux", "qemu", "opensbi", "kvmtool", "pack", "verify", "run"))
    parser.add_argument("-j", "--jobs", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.jobs < 1 or (args.dry_run and args.action != "run"):
        parser.error("jobs must be positive; dry-run only applies to run")
    require_checkout()
    if args.action == "prepare":
        prepare()
    elif args.action == "check":
        check()
    elif args.action == "build":
        prepare()
        check()
        for name in ("linux", "opensbi", "qemu", "kvmtool"):
            build_component(name, args.jobs)
        pack()
    elif args.action == "pack":
        pack()
    elif args.action == "verify":
        verify()
    elif args.action == "run":
        launch(args.dry_run)
    else:
        build_component(args.action, args.jobs)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError, ValueError) as error:
        sys.exit(f"STOP: {error}")
