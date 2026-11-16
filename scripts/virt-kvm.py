#!/usr/bin/env python3
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "build" / "virt-kvm"
SDK = Path(os.environ.get("SOURCE_SDK", str(ROOT))).resolve()
SOURCE_LOCK = ROOT / "conf/pmp-virt/sources.json"
RAM_BASE = 0x80000000
RAM_SIZE = 2048 * 1024 * 1024
LOAD_ADDRESS = 0x80200000
SOURCES = json.loads(SOURCE_LOCK.read_text())["sources"]
DIRECT = {"linux-host", "opensbi", "qemu"}
SCRIPT_INPUTS = ("scripts/virt-kvm.py", "scripts/run-virt-guest.sh",
                 "scripts/run-virt-debian.sh", "tests/pmp-virt/check-host.sh",
                 "tests/pmp-virt/check-guest.sh", "tests/pmp-virt/run-host-suite.sh",
                 "tests/pmp-virt/guest-autorun.sh", "tests/pmp-virt/syscall-api.c")
DISABLED = ("MODULES", "JUMP_LABEL", "FUNCTION_TRACER", "FUNCTION_GRAPH_TRACER", "DYNAMIC_FTRACE", "FTRACE", "KPROBES", "LIVEPATCH", "BPF_JIT", "RANDOMIZE_BASE", "KEXEC", "KEXEC_FILE", "KGDB")


def fail(message):
    raise RuntimeError(message)


def run(arguments, cwd=None, capture=False, env=None):
    arguments = [str(argument) for argument in arguments]
    if not capture:
        print("+ " + shlex.join(arguments), flush=True)
    return subprocess.run(arguments, cwd=cwd, env=env, check=True,
                          stdout=subprocess.PIPE if capture else None,
                          text=True).stdout


def digest(path):
    checksum = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def private_path(path):
    path = Path(path).resolve()
    expected = ROOT / "build" / "virt-kvm"
    if not path.is_relative_to(expected):
        fail(f"Output must stay inside {expected}: {path}")
    return path


def write_json(path, value):
    path = private_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def verify_inputs():
    state = json.loads(SOURCE_LOCK.read_text())
    if state.get("schema") != 1 or state.get("sources") != SOURCES:
        fail("Source lock changed during this process; restart after reviewing it")
    for filename in ("conf/pmp-virt/linux.config", "tests/pmp-virt/user-exec.c", *SCRIPT_INPUTS):
        if not (ROOT / filename).is_file():
            fail(f"Missing SDK input: {filename}")


def require_checkout():
    top = Path(run(["git", "-C", ROOT, "rev-parse", "--show-toplevel"], capture=True).strip()).resolve()
    if top != ROOT:
        fail("Run the entry point from an SDK Git checkout")


def checked_submodule(name):
    # Guest reuses Linux history but builds an upstream commit in a private clone.
    details = SOURCES["linux-host" if name == "linux-guest" else name]
    relative = details["path"]
    expected = details["revision"]
    source = ROOT / relative
    if not (source / ".git").exists():
        fail(f"Submodule is not initialized: {relative}. Run prepare or git submodule update --init -- {relative}")
    if source.is_symlink() or source.resolve() != ROOT / relative:
        fail(f"Unexpected submodule path: {source}")
    top = Path(run(["git", "-C", source, "rev-parse", "--show-toplevel"], capture=True).strip()).resolve()
    if top != source:
        fail(f"Not a component Git checkout: {source}")
    index = run(["git", "-C", ROOT, "ls-files", "--stage", "--", relative], capture=True).split()
    if len(index) != 4 or index[:3] != ["160000", expected, "0"]:
        fail(f"SDK gitlink disagrees with source lock: {relative}")
    if run(["git", "-C", source, "rev-parse", "HEAD"], capture=True).strip() != expected:
        fail(f"Submodule revision mismatch: {relative}; preserve local work and inspect")
    if run(["git", "-C", source, "status", "--porcelain", "--untracked-files=all"], capture=True).strip():
        fail(f"Submodule has local changes: {relative}; commit/review them and update its lock before building")
    return source


def local_repository(name):
    return checked_submodule(name)


def toolchain_command(arguments, input_text=None):
    try:
        result = subprocess.run(arguments, input=input_text, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        fail(f"Cannot run {arguments[0]}: {error}")
    if result.returncode:
        fail(f"{arguments[0]} failed: {result.stdout.strip()[-1200:]}")
    return result.stdout.strip()


def probe_toolchain(candidate):
    compiler = shutil.which(candidate + "gcc")
    if not compiler:
        fail(f"Compiler entry not found: {candidate}gcc")
    prefix = str(Path(compiler).absolute())[:-3]
    toolchain_command([prefix + "gcc", "--version"])
    target = toolchain_command([prefix + "gcc", "-dumpmachine"])
    if not target.startswith("riscv64-") or "linux" not in target.split("-"):
        fail(f"Expected a RISC-V 64-bit Linux compiler, found {target}")
    for tool in ("as", "ld", "ar", "nm", "objcopy", "objdump", "readelf", "strip"):
        toolchain_command([prefix + tool, "--version"])
    private_path(WORK).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="toolchain-probe-", dir=WORK) as temporary:
        executable = Path(temporary) / "probe"
        program = '#include <stdio.h>\nint main(void) { return puts("virt-kvm toolchain probe") < 0; }\n'
        toolchain_command([prefix + "gcc", "-x", "c", "-", "-static", "-o", str(executable)], program)
        try:
            elf_machine(executable, 243)
        except OSError as error:
            fail(f"Compiler did not produce a readable executable: {error}")
    print(f"Cross compiler, binutils and static RISC-V link: PASS ({prefix})", flush=True)
    return prefix


def cross_prefix():
    explicit = os.environ.get("CROSS_COMPILE")
    if explicit is not None:
        if not explicit:
            fail("CROSS_COMPILE is empty; unset it or specify an installed tool prefix")
        try:
            return probe_toolchain(explicit)
        except RuntimeError as error:
            fail(f"Explicit CROSS_COMPILE is unusable: {error}")
    candidates = [str(SDK / "toolchain/bin/riscv64-unknown-linux-gnu-"),
                  str(SDK / "rootfs/buildroot_initramfs/host/bin/riscv64-linux-"),
                  "riscv64-linux-gnu-"]
    errors = []
    for candidate in candidates:
        try:
            return probe_toolchain(candidate)
        except RuntimeError as error:
            errors.append(f"{candidate}: {error}")
            print(f"Skipping unusable toolchain: {errors[-1]}", flush=True)
    fail("No usable cross compiler. Set CROSS_COMPILE to an installed RISC-V Linux tool prefix.\n" + "\n".join(errors))


def base_rootfs():
    candidates = [Path(os.environ["BASE_ROOTFS"])] if "BASE_ROOTFS" in os.environ else [
        SDK / "images/base/rootfs.cpio.gz",
        SDK / "rootfs/buildroot_initramfs/images/rootfs.cpio.gz",
        Path.home() / "work/my_core_files/rootfs-devtmpfs.cpio.gz"]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    fail("No base initramfs. Set BASE_ROOTFS to an existing rootfs.cpio.gz.")


def validate_rootfs(base):
    decompressor = subprocess.Popen(["gzip", "-cd", str(base)], stdout=subprocess.PIPE)
    try:
        listing = subprocess.run(["cpio", "-it", "--quiet"], stdin=decompressor.stdout,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    finally:
        decompressor.stdout.close()
        status = decompressor.wait()
    if status or listing.returncode:
        fail(f"Invalid gzip/newc base initramfs: {base}")
    names = {name.removeprefix("./").rstrip("/") for name in listing.stdout.splitlines()}
    for required in ("sbin/init", "bin/sh", "bin/mount", "bin/echo", "sbin/getty"):
        if required not in names:
            fail(f"Base initramfs lacks {required}")
    print(f"Base initramfs archive and init tools: PASS ({base})", flush=True)


def verify_source(name):
    original = checked_submodule(name)
    if name in DIRECT:
        return original
    source = private_path(WORK / "src" / name)
    marker = WORK / "state" / (name + ".json")
    if not marker.is_file():
        fail(f"Private build source is not prepared: {source}; run prepare")
    state = json.loads(marker.read_text())
    expected = SOURCES[name]["revision"]
    if state != {"schema": 2, "revision": expected}:
        fail(f"Old or mismatched source state: {source}; preserve it and use a fresh build directory")
    top = Path(run(["git", "-C", source, "rev-parse", "--show-toplevel"], capture=True).strip()).resolve()
    if top != source or run(["git", "-C", source, "rev-parse", "HEAD"], capture=True).strip() != expected:
        fail(f"Private source revision mismatch: {source}")
    if run(["git", "-C", source, "status", "--porcelain", "--untracked-files=all"], capture=True).strip():
        fail(f"Private source has unexpected changes: {source}")
    return source


def ram_header():
    if RAM_SIZE < 8 or RAM_SIZE & (RAM_SIZE - 1) or RAM_BASE % RAM_SIZE:
        fail("RAM must be a naturally aligned NAPOT region")
    napot = (RAM_BASE >> 2) | ((RAM_SIZE >> 3) - 1)
    return (f"#define PV_RAM_BASE 0x{RAM_BASE:x}UL\n"
            f"#define PV_RAM_LIMIT 0x{RAM_BASE + RAM_SIZE:x}UL\n"
            f"#define PV_RAM_NAPOT 0x{napot:x}UL\n")


def prepare_source(name):
    relative = SOURCES[name]["path"]
    source = ROOT / relative
    if not (source / ".git").exists():
        if source.exists() and any(source.iterdir()):
            fail(f"Uninitialized submodule contains files; preserve and inspect: {source}")
        # Follow the SDK gitlink, never --remote or a floating branch.
        run(["git", "-C", ROOT, "submodule", "update", "--init", "--depth=1", "--", relative])
    original = checked_submodule(name)
    if name in DIRECT:
        return original
    target = private_path(WORK / "src" / name)
    if target.exists():
        return verify_source(name)
    revision = SOURCES[name]["revision"]
    contains = subprocess.run(["git", "-C", str(original), "cat-file", "-e", revision + "^{commit}"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if contains.returncode:
        run(["git", "-C", original, "fetch", "--depth=1", SOURCES[name]["url"], revision])
        run(["git", "-C", original, "cat-file", "-e", revision + "^{commit}"])
    target.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", "--shared", "--no-checkout", "--", original, target])
    run(["git", "-C", target, "checkout", "--detach", revision])
    write_json(WORK / "state" / (name + ".json"), {"schema": 2, "revision": revision})
    return verify_source(name)


def check():
    verify_inputs()
    print(f"SDK: {ROOT}\nOutputs: {WORK}\nSource cache: {SDK}")
    errors = []
    for executable in ("git", "make", "gcc", "g++", "python3", "cpio", "gzip", "pkg-config"):
        print(f"{executable}: {shutil.which(executable) or 'MISSING'}")
        if not shutil.which(executable):
            errors.append(f"Missing build tool: {executable}")
    for name in SOURCES:
        try:
            print(f"{name}: {checked_submodule(name)} @ {SOURCES[name]['revision']}")
        except RuntimeError as error:
            errors.append(str(error))
    for label, lookup in (("CROSS_COMPILE", cross_prefix), ("BASE_ROOTFS", base_rootfs)):
        try:
            print(f"{label}: {lookup()}")
        except RuntimeError as error:
            errors.append(str(error))
    print(f"Free disk: {shutil.disk_usage(ROOT).free // (1024 ** 3)} GiB")
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        fail("Preflight needs the inputs listed above; no sources were modified.")


def configure_linux(name, cross):
    source = verify_source(name)
    output = private_path(WORK / "out" / name)
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "conf/pmp-virt/linux.config", output / ".config")
    config = [source / "scripts/config", "--file", output / ".config"]
    for symbol in DISABLED:
        run(config + ["--disable", symbol])
    for symbol in ("VIRTUALIZATION", "KVM"):
        run(config + ["--enable" if name == "linux-host" else "--disable", symbol])
    run(config + ["--set-str", "LOCALVERSION", "-pmpvirt-kvm-host" if name == "linux-host" else "-virt-kvm-guest"])
    run(config + ["--disable", "LOCALVERSION_AUTO"])
    run(config + ["--set-str", "INITRAMFS_SOURCE", ""])
    run(["make", "-C", source, f"O={output}", "ARCH=riscv", f"CROSS_COMPILE={cross}", "olddefconfig"])
    content = (output / ".config").read_text()
    for symbol in DISABLED:
        if f"CONFIG_{symbol}=y\n" in content or f"CONFIG_{symbol}=m\n" in content:
            fail(f"Dynamic-code option remains enabled: {symbol}")
    expected = ["CONFIG_BLK_DEV_INITRD=y", "CONFIG_DEVTMPFS=y", "CONFIG_SERIAL_8250_CONSOLE=y", "CONFIG_VIRTIO_MMIO=y", "CONFIG_STRICT_KERNEL_RWX=y",
                "CONFIG_VIRTIO_BLK=y", "CONFIG_VIRTIO_NET=y", "CONFIG_EXT4_FS=y",
                "CONFIG_NET=y", "CONFIG_INET=y"]
    if name == "linux-host":
        expected.append("CONFIG_KVM=y")
    elif "CONFIG_KVM=y" in content.splitlines() or "CONFIG_KVM=m" in content.splitlines():
        fail("The ordinary guest must not enable KVM")
    for setting in expected:
        if setting not in content.splitlines():
            fail(f"Required {name} config missing: {setting}")
    return source, output


def layout_header(image, system_map):
    symbols = {}
    for line in Path(system_map).read_text().splitlines():
        fields = line.split()
        if len(fields) == 3:
            symbols[fields[2]] = int(fields[0], 16)
    required = ("_start", "_text", "_etext", "__start_rodata", "_data")
    if any(symbol not in symbols for symbol in required):
        fail("System.map lacks required layout symbols")
    offset = LOAD_ADDRESS - symbols["_start"]
    text_start = symbols["_text"] + offset
    text_limit = (symbols["_etext"] + offset + 4095) & ~4095
    ro_start = symbols["__start_rodata"] + offset
    ro_limit = symbols["_data"] + offset
    if not LOAD_ADDRESS <= text_start < text_limit <= ro_start < ro_limit < RAM_BASE + RAM_SIZE:
        fail("Host layout is outside the trusted RAM range")
    if any(value % 4096 for value in (text_start, text_limit, ro_start, ro_limit)):
        fail("Host layout is not page aligned")
    with Path(image).open("rb") as stream:
        image_header = stream.read(64)
    if len(image_header) != 64 or image_header[56:60] != b"RSC\x05":
        fail("Expected an uncompressed RISC-V Linux Image")
    header = ""
    for name, value in (("TEXT_START", text_start), ("TEXT_LIMIT", text_limit), ("RO_START", ro_start), ("RO_LIMIT", ro_limit)):
        header += f"#define PV_{name} 0x{value:x}UL\n"
    return header + f'#define PV_IMAGE_SHA "{digest(image)}"\n' + ram_header()


def build_firmware(cross, jobs):
    source = verify_source("opensbi")
    host = WORK / "out/linux-host"
    header_path = private_path(WORK / "generated/pmp_virt_layout.h")
    header_path.parent.mkdir(parents=True, exist_ok=True)
    header_path.write_text(layout_header(host / "arch/riscv/boot/Image", host / "System.map"))
    if any(character.isspace() or character in '\\"' for character in header_path.as_posix()):
        fail("OpenSBI generated layout path must not contain whitespace, backslashes or quotes")
    output = private_path(WORK / "out/opensbi")
    run(["make", "-C", source, f"O={output}", "PLATFORM=generic", "PLATFORM_RISCV_XLEN=64",
         "PLATFORM_DEFCONFIG=pmp_virt_seal_defconfig", f"CROSS_COMPILE={cross}",
         "FW_TEXT_START=0x80000000", "FW_JUMP_ADDR=0x80200000",
         f"PMP_VIRT_LAYOUT_HEADER={header_path.as_posix()}", f"-j{jobs}"])
    config = (output / "platform/generic/kconfig/.config").read_text().splitlines()
    if "CONFIG_PMP_VIRT_SEAL=y" not in config or "CONFIG_PMP_VIRT_TRANSPORT_TEST=y" in config:
        fail("OpenSBI seal configuration mismatch")


def append_archive(base, staging, destination):
    # BusyBox cpio stops at the first TRAILER record. Extract the base archive,
    # merge the overlay, then emit one cpio stream so overlay files are visible.
    with gzip.open(base, "rb") as stream:
        base_archive = stream.read()
    with tempfile.TemporaryDirectory(prefix="merge-", dir=WORK) as merged_name:
        merged = Path(merged_name)
        subprocess.run(["cpio", "-idm", "--no-absolute-filenames"], cwd=merged,
                       input=base_archive, stdout=subprocess.DEVNULL, check=True)
        shutil.copytree(staging, merged, dirs_exist_ok=True)
        listing = ["."] + ["./" + str(path.relative_to(merged)).replace(os.sep, "/")
                           for path in sorted(merged.rglob("*"))]
        archive = subprocess.run(["cpio", "--null", "-o", "-H", "newc", "--owner=0:0"],
                                 cwd=merged, input=("\0".join(listing) + "\0").encode(),
                                 stdout=subprocess.PIPE, check=True).stdout
    destination = private_path(destination)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    with temporary.open("wb") as stream:
        with gzip.GzipFile(fileobj=stream, mode="wb", filename="", mtime=0) as compressor:
            compressor.write(archive)
    temporary.replace(destination)


def install(source, target, executable=False):
    target.parent.mkdir(parents=True, exist_ok=True)
    data = Path(source).read_bytes()
    # Shell entrypoints must use Unix LF endings; a CR in #!/bin/sh makes the
    # kernel report the script as "not found" even when it is present.
    if executable and data.startswith(b"#!"):
        data = data.replace(b"\r\n", b"\n")
    target.write_bytes(data)
    target.chmod(0o755 if executable else 0o644)


def elf_machine(path, expected):
    with Path(path).open("rb") as stream:
        header = stream.read(64)
        if len(header) != 64 or header[:6] != b"\x7fELF\x02\x01" or int.from_bytes(header[18:20], "little") != expected:
            fail(f"Unexpected ELF architecture: {path}")
        table_offset = int.from_bytes(header[32:40], "little")
        entry_size = int.from_bytes(header[54:56], "little")
        entry_count = int.from_bytes(header[56:58], "little")
        if not entry_count or entry_count > 1024 or entry_size < 56 or table_offset + entry_count * entry_size > Path(path).stat().st_size:
            fail(f"Invalid ELF program headers: {path}")
        for index in range(entry_count):
            stream.seek(table_offset + index * entry_size)
            if int.from_bytes(stream.read(4), "little") == 3:
                fail(f"Expected a static RISC-V executable, found PT_INTERP: {path}")


def package_rootfs(base):
    images = private_path(WORK / "images")
    images.mkdir(parents=True, exist_ok=True)
    elf_machine(WORK / "src/kvmtool/lkvm-static", 243)
    elf_machine(WORK / "out/pv-user-test", 243)
    elf_machine(WORK / "out/pv-syscall-api", 243)
    with tempfile.TemporaryDirectory(prefix="pack-", dir=WORK) as temporary:
        staging = Path(temporary)
        install(ROOT / "conf/rootfs-overlay/etc/inittab", staging / "etc/inittab")
        with (staging / "etc/inittab").open("a") as stream:
            stream.write("\n::sysinit:/bin/echo VIRT-KVM GUEST BOOTED\n")
        install(ROOT / "tests/pmp-virt/check-guest.sh", staging / "usr/bin/check-virt-guest", True)
        install(ROOT / "tests/pmp-virt/guest-autorun.sh", staging / "usr/bin/virt-guest-autorun", True)
        with (staging / "etc/inittab").open("a") as stream:
            stream.write("::sysinit:/usr/bin/virt-guest-autorun\n")
        append_archive(base, staging, images / "guest-rootfs.cpio.gz")
    with tempfile.TemporaryDirectory(prefix="pack-", dir=WORK) as temporary:
        staging = Path(temporary)
        install(ROOT / "conf/rootfs-overlay/etc/inittab", staging / "etc/inittab")
        install(WORK / "src/kvmtool/lkvm-static", staging / "usr/bin/lkvm", True)
        install(WORK / "out/pv-user-test", staging / "usr/bin/pv-user-test", True)
        install(WORK / "out/pv-syscall-api", staging / "usr/bin/pv-syscall-api", True)
        install(ROOT / "tests/pmp-virt/check-host.sh", staging / "usr/bin/check-virt-host", True)
        install(ROOT / "scripts/run-virt-guest.sh", staging / "usr/bin/run-virt-guest", True)
        install(ROOT / "scripts/run-virt-debian.sh", staging / "usr/bin/run-virt-debian", True)
        install(ROOT / "tests/pmp-virt/run-host-suite.sh", staging / "usr/bin/test-virt-all", True)
        install(WORK / "out/linux-guest/arch/riscv/boot/Image", staging / "opt/guest/Image")
        install(images / "guest-rootfs.cpio.gz", staging / "opt/guest/rootfs.cpio.gz")
        append_archive(base, staging, images / "host-rootfs.cpio.gz")


def artifact_paths():
    return [WORK / path for path in (
        "out/linux-host/arch/riscv/boot/Image", "out/linux-host/.config", "out/linux-host/System.map",
        "out/linux-guest/arch/riscv/boot/Image", "out/linux-guest/.config",
        "out/opensbi/platform/generic/firmware/fw_jump.bin", "out/opensbi/platform/generic/kconfig/.config",
        "out/qemu/qemu-system-riscv64", "out/pv-user-test", "out/pv-syscall-api", "src/kvmtool/lkvm-static",
        "generated/pmp_virt_layout.h", "images/host-rootfs.cpio.gz", "images/guest-rootfs.cpio.gz"
    )] + [ROOT / filename for filename in (
        "conf/pmp-virt/linux.config", "conf/pmp-virt/sources.json", "conf/rootfs-overlay/etc/inittab",
        "tests/pmp-virt/user-exec.c", *SCRIPT_INPUTS)]


def manifest(base=None, cross=None, compiler_version=None):
    files = {path.relative_to(ROOT).as_posix(): digest(path) for path in artifact_paths()}
    state = {"schema": 2, "ram_mib": RAM_SIZE // (1024 * 1024),
             "sources": {name: details["revision"] for name, details in SOURCES.items()}, "files": files}
    if base:
        state["base_rootfs"] = {"path": str(base), "sha256": digest(base)}
    if cross:
        state["compiler"] = run([cross + "gcc", "--version"], capture=True).splitlines()[0]
    elif compiler_version is not None:
        state["compiler"] = compiler_version
    write_json(WORK / "manifest.json", state)


def verify(allow_script_updates=False, allow_test_upgrade=False):
    verify_inputs()
    state = json.loads((WORK / "manifest.json").read_text())
    expected_paths = {path.relative_to(ROOT).as_posix() for path in artifact_paths()}
    recorded_paths = set(state["files"])
    added_tests = {"tests/pmp-virt/syscall-api.c", "build/virt-kvm/out/pv-syscall-api"}
    acceptable_paths = recorded_paths == expected_paths or (
        allow_test_upgrade and recorded_paths == expected_paths - added_tests)
    if state.get("schema") != 2 or state.get("ram_mib") != 2048 or not acceptable_paths:
        fail("Artifact manifest format, RAM size, or file list mismatch")
    if state["sources"] != {name: details["revision"] for name, details in SOURCES.items()}:
        fail("Artifact source revision mismatch")
    script_inputs = set(SCRIPT_INPUTS)
    for filename, expected in state["files"].items():
        if allow_script_updates and filename in script_inputs:
            continue
        if digest(ROOT / filename) != expected:
            fail(f"Artifact checksum mismatch: {filename}. Rebuild before booting.")
    host = WORK / "out/linux-host"
    expected_header = layout_header(host / "arch/riscv/boot/Image", host / "System.map")
    if (WORK / "generated/pmp_virt_layout.h").read_text() != expected_header:
        fail("Firmware layout does not match the host Image")
    firmware = WORK / "out/opensbi/platform/generic/firmware/fw_jump.bin"
    if digest(host / "arch/riscv/boot/Image").encode() not in firmware.read_bytes():
        fail("Compiled firmware does not contain the current host Image digest")
    label = "Existing artifacts and host/firmware layout" if allow_script_updates else "Artifact hashes and host/firmware layout"
    print(label + ": PASS", flush=True)


def repack():
    verify(allow_script_updates=True)
    previous = json.loads((WORK / "manifest.json").read_text())
    base = Path(previous["base_rootfs"]["path"])
    if digest(base) != previous["base_rootfs"]["sha256"]:
        fail("The original base initramfs has changed; inspect before repacking")
    validate_rootfs(base)
    package_rootfs(base)
    manifest(base, compiler_version=previous.get("compiler"))
    verify()
    print("Rootfs repacked. Existing kernel, firmware and QEMU binaries were preserved.")


def compile_tests(cross):
    for source, binary in (("user-exec.c", "pv-user-test"),
                           ("syscall-api.c", "pv-syscall-api")):
        run([cross + "gcc", "-O2", "-Wall", "-Wextra", "-static",
             ROOT / "tests/pmp-virt" / source, "-o", WORK / "out" / binary])


def rebuild_tests():
    # Permit only the two newly introduced test paths to be absent from an
    # older schema-2 manifest. Every existing non-script artifact must match.
    verify(allow_script_updates=True, allow_test_upgrade=True)
    previous = json.loads((WORK / "manifest.json").read_text())
    base = Path(previous["base_rootfs"]["path"])
    if digest(base) != previous["base_rootfs"]["sha256"]:
        fail("The original base initramfs has changed; inspect before rebuilding tests")
    validate_rootfs(base)
    cross = cross_prefix()
    compile_tests(cross)
    package_rootfs(base)
    manifest(base, cross)
    verify()
    print("Tests rebuilt and rootfs repacked; kernel, firmware and QEMU were preserved.")


def build(jobs):
    verify_inputs()
    cross = cross_prefix()
    base = base_rootfs()
    validate_rootfs(base)
    run([cross + "gcc", "--version"])
    for name in SOURCES:
        prepare_source(name)
    for name in ("linux-host", "linux-guest"):
        source, output = configure_linux(name, cross)
        run(["make", "-C", source, f"O={output}", "ARCH=riscv", f"CROSS_COMPILE={cross}", f"-j{jobs}", "Image"])
    build_firmware(cross, jobs)
    qemu_source = verify_source("qemu")
    qemu_output = private_path(WORK / "out/qemu")
    qemu_output.mkdir(parents=True, exist_ok=True)
    run([qemu_source / "configure", "--target-list=riscv64-softmmu", "--disable-docs", "--enable-slirp", "--enable-download"], cwd=qemu_output)
    run(["make", f"-j{jobs}"], cwd=qemu_output)
    dtc = verify_source("dtc")
    run(["make", "-C", dtc, "-B", f"CC={cross}gcc", f"AR={cross}ar",
         "NO_VALGRIND=1", "NO_YAML=1", f"-j{jobs}", "libfdt"])
    lkvm = verify_source("kvmtool")
    run(["make", "-C", lkvm, "ARCH=riscv", f"CROSS_COMPILE={cross}", f"LIBFDT_DIR={dtc / 'libfdt'}", f"-j{jobs}", "lkvm-static"])
    compile_tests(cross)
    package_rootfs(base)
    manifest(base, cross)
    verify()
    for name in SOURCES:
        verify_source(name)
    print("Build complete. Runtime validation has NOT been performed.")


def launch(dry_run):
    verify()
    command = [WORK / "out/qemu/qemu-system-riscv64", "-machine", "virt", "-accel", "tcg",
               "-cpu", "rv64,h=true,smepmp=off,x-pmp-virt=on", "-m", "2048M", "-smp", "1", "-nographic",
               "-bios", WORK / "out/opensbi/platform/generic/firmware/fw_jump.bin",
               "-kernel", WORK / "out/linux-host/arch/riscv/boot/Image",
               "-initrd", WORK / "images/host-rootfs.cpio.gz",
               "-append", "console=ttyS0 earlycon=sbi rdinit=/sbin/init maxcpus=1"]
    disk_name = os.environ.get("VIRT_DEBIAN_DISK")
    if disk_name:
        disk = Path(disk_name).expanduser().resolve()
        if not disk.is_file():
            fail(f"Debian disk not found: {disk}")
        if not os.access(disk, os.R_OK | os.W_OK):
            fail(f"Debian disk is not readable/writable: {disk}")

        # QEMU 的参数以逗号分隔，路径中的逗号需要转义。
        disk_path = str(disk).replace(",", ",,")
        command.extend([
            "-drive",
            f"file={disk_path},format=raw,if=none,id=debian",
            "-device",
            "virtio-blk-device,drive=debian",
            "-netdev", "user,id=hostnet",
            "-device", "virtio-net-device,netdev=hostnet",
        ])
    print(shlex.join([str(argument) for argument in command]), flush=True)
    if not dry_run:
        os.execv(str(command[0]), [str(argument) for argument in command])


def main():
    parser = argparse.ArgumentParser(description="Isolated PMP.Virt host + ordinary KVM guest, B1 integration")
    parser.add_argument("action", choices=("check", "prepare", "build", "repack", "rebuild-tests", "verify", "run"))
    parser.add_argument("-j", "--jobs", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("jobs must be positive")
    if args.dry_run and args.action != "run":
        parser.error("--dry-run is only supported for run")
    private_path(WORK)
    require_checkout()
    if args.action in ("prepare", "build", "repack", "rebuild-tests", "run") and platform.system() != "Linux" and not args.dry_run:
        fail("Build and run these steps in the Ubuntu server terminal")
    if args.action == "check":
        check()
    elif args.action == "prepare":
        verify_inputs()
        for name in SOURCES:
            prepare_source(name)
    elif args.action == "build":
        build(args.jobs)
    elif args.action == "repack":
        repack()
    elif args.action == "rebuild-tests":
        rebuild_tests()
    elif args.action == "verify":
        verify()
    else:
        launch(args.dry_run)


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"STOP: {error}", file=sys.stderr)
        sys.exit(1)
