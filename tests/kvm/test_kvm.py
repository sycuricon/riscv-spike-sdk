import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import json
import gzip
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
build = load("kvm_build", ROOT / "scripts/kvm.py")
regression = load("kvm_regression", ROOT / "tests/kvm/run-regression.py")

class Checks(unittest.TestCase):
    def test_compiler_rejects_bare_metal_target(self):
        with patch.object(build.shutil, "which", return_value="/tool/bin/riscv64-unknown-elf-gcc"), \
             patch.object(build, "output", return_value="riscv64-unknown-elf"):
            with self.assertRaisesRegex(RuntimeError, "Linux compiler"):
                build.compiler()

    @unittest.skipUnless(shutil.which("cpio"), "cpio is required")
    def test_base_rootfs_rejects_missing_files_and_wrong_architecture(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = root / "base.gz"
            stage = root / "stage"
            stage.mkdir()
            def archive(names):
                result = subprocess.run(["cpio", "-o", "-H", "newc", "--quiet"],
                                        cwd=stage, input="\n".join(names).encode() + b"\n",
                                        stdout=subprocess.PIPE, check=True)
                with gzip.open(base, "wb") as stream:
                    stream.write(result.stdout)
            archive(["."])
            with self.assertRaisesRegex(RuntimeError, "missing required"):
                build.validate_rootfs(base)
            names = ["sbin/init", "bin/sh", "bin/mount", "sbin/getty", "sbin/modprobe",
                     "sbin/udhcpc", "sbin/poweroff", "etc/init.d/rcS", "etc/init.d/rcK",
                     "bin/awk", "bin/sleep", "bin/cat", "bin/uname", "bin/busybox"]
            for name in names:
                path = stage / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"wrong architecture")
            archive(names)
            with self.assertRaisesRegex(RuntimeError, "RV64 ELF"):
                build.validate_rootfs(base)
            elf = bytearray(64)
            elf[:6] = b"\x7fELF\x02\x01"
            elf[18:20] = (243).to_bytes(2, "little")
            (stage / "bin/busybox").write_bytes(elf)
            archive(names)
            build.validate_rootfs(base)

    def test_transcript_requires_every_step_in_order(self):
        good = "\r\n".join(regression.STEPS) + "\r\n"
        regression.check_transcript(good)
        for marker in regression.STEPS:
            with self.subTest(marker=marker), self.assertRaises(RuntimeError):
                regression.check_transcript(good.replace(marker, "# echo " + marker))
        with self.assertRaises(RuntimeError):
            regression.check_transcript(good + "Kernel panic\n")

    def test_manifest_detects_tampered_and_missing_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work = root / "build/kvm"
            work.mkdir(parents=True)
            files = {}
            for name in (*build.INPUTS, *("build/kvm/" + p for p in build.OUTPUTS)):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"expected")
                files[name] = build.digest(path)
            state = {"schema":1,"sources":build.SOURCES,"files":files}
            manifest = work / "manifest.json"
            manifest.write_text(json.dumps(state))
            with patch.object(build,"ROOT",root), patch.object(build,"WORK",work), patch.object(build,"source"):
                build.verify()
                target = root / "build/kvm/linux/arch/riscv/boot/Image"
                target.write_bytes(b"tampered")
                with self.assertRaisesRegex(RuntimeError,"checksum"):
                    build.verify()
                del state["files"]["build/kvm/linux/arch/riscv/boot/Image"]
                manifest.write_text(json.dumps(state))
                with self.assertRaisesRegex(RuntimeError,"file list"):
                    build.verify()
