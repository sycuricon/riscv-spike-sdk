import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("build_sdk_tests", ROOT / "scripts/virt-kvm.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
spec = importlib.util.spec_from_file_location("regression_tests", ROOT / "tests/pmp-virt/run-regression.py")
regression = importlib.util.module_from_spec(spec)
spec.loader.exec_module(regression)


def git(path, *args):
    return subprocess.check_output(["git", "-C", str(path), *args], text=True).strip()


class BuildChecks(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name).resolve()
        self.context = patch.multiple(build, ROOT=self.root, WORK=self.root / "build/virt-kvm",
                                      SOURCE_LOCK=self.root / "conf/pmp-virt/sources.json")
        self.context.start()
        self.image = self.root / "Image"
        header = bytearray(64)
        header[56:60] = b"RSC\x05"
        self.image.write_bytes(header)
        self.system_map = self.root / "System.map"
        self.symbols()

    def tearDown(self):
        self.context.stop()
        self.directory.cleanup()

    def symbols(self, **overrides):
        values = dict(_start=0xffffffff80000000, _text=0xffffffff80002000,
                      _etext=0xffffffff805ffff1, __start_rodata=0xffffffff80800000,
                      _data=0xffffffff80c00000)
        values.update(overrides)
        self.system_map.write_text("".join(f"{value:x} T {key}\n" for key, value in values.items()))

    def fixture(self):
        for path in build.artifact_paths():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fixture")
        build.SOURCE_LOCK.write_text(json.dumps({"schema": 1, "sources": build.SOURCES}))
        host = build.WORK / "out/linux-host"
        (host / "arch/riscv/boot/Image").write_bytes(self.image.read_bytes())
        (host / "System.map").write_bytes(self.system_map.read_bytes())
        (build.WORK / "generated/pmp_virt_layout.h").write_text(build.layout_header(self.image, self.system_map))
        (build.WORK / "out/opensbi/platform/generic/firmware/fw_jump.bin").write_bytes(build.digest(self.image).encode())
        build.manifest()

    def test_layout_final_image_and_2g_ram(self):
        header = build.layout_header(self.image, self.system_map)
        self.assertIn("PV_TEXT_START 0x80202000UL", header)
        self.assertIn("PV_TEXT_LIMIT 0x80800000UL", header)
        self.assertIn("PV_RAM_LIMIT 0x100000000UL", header)
        self.assertIn("PV_RAM_NAPOT 0x2fffffffUL", header)
        self.assertIn(build.digest(self.image), header)

    def test_layout_rejects_overlap(self):
        self.symbols(__start_rodata=0xffffffff80400000)
        with self.assertRaises(RuntimeError):
            build.layout_header(self.image, self.system_map)

    def test_layout_rejects_alignment(self):
        self.symbols(__start_rodata=0xffffffff80800001)
        with self.assertRaises(RuntimeError):
            build.layout_header(self.image, self.system_map)

    def test_layout_rejects_missing_symbols(self):
        self.system_map.write_text("")
        with self.assertRaises(RuntimeError):
            build.layout_header(self.image, self.system_map)

    def test_layout_rejects_outside_ram(self):
        self.symbols(_data=0xffffffffffe00000)
        with self.assertRaises(RuntimeError):
            build.layout_header(self.image, self.system_map)

    def test_layout_rejects_invalid_image(self):
        self.image.write_bytes(bytes(64))
        with self.assertRaises(RuntimeError):
            build.layout_header(self.image, self.system_map)

    def test_output_cannot_escape(self):
        with self.assertRaises(RuntimeError):
            build.private_path(self.root / "repo/opensbi")

    def test_manifest_matching(self):
        self.fixture()
        build.verify()

    def test_manifest_rejects_old_schema(self):
        self.fixture()
        path = build.WORK / "manifest.json"
        state = json.loads(path.read_text())
        state["schema"] = 1
        path.write_text(json.dumps(state))
        with self.assertRaises(RuntimeError):
            build.verify()

    def test_test_upgrade_only_accepts_known_added_files(self):
        self.fixture()
        path = build.WORK / "manifest.json"
        state = json.loads(path.read_text())
        for name in ("tests/pmp-virt/syscall-api.c", "build/virt-kvm/out/pv-syscall-api"):
            del state["files"][name]
        path.write_text(json.dumps(state))
        with self.assertRaises(RuntimeError):
            build.verify()
        build.verify(allow_script_updates=True, allow_test_upgrade=True)
        del state["files"]["build/virt-kvm/out/linux-host/arch/riscv/boot/Image"]
        path.write_text(json.dumps(state))
        with self.assertRaises(RuntimeError):
            build.verify(allow_script_updates=True, allow_test_upgrade=True)

    def test_test_upgrade_still_rejects_changed_kernel(self):
        self.fixture()
        (build.WORK / "out/linux-host/arch/riscv/boot/Image").write_bytes(b"changed")
        with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
            build.verify(allow_script_updates=True, allow_test_upgrade=True)

    def test_manifest_rejects_changed_image(self):
        self.fixture()
        (build.WORK / "out/linux-host/arch/riscv/boot/Image").write_bytes(b"wrong")
        with self.assertRaises(RuntimeError):
            build.verify()

    def test_manifest_rejects_stale_firmware(self):
        self.fixture()
        (build.WORK / "out/opensbi/platform/generic/firmware/fw_jump.bin").write_bytes(b"stale")
        build.manifest()
        with self.assertRaisesRegex(RuntimeError, "Compiled firmware"):
            build.verify()

    def test_repack_rejects_changed_base(self):
        self.fixture()
        base = self.root / "base.cpio.gz"
        base.write_bytes(b"old")
        build.manifest(base)
        base.write_bytes(b"new")
        with patch.object(build, "package_rootfs") as pack:
            with self.assertRaisesRegex(RuntimeError, "base initramfs"):
                build.repack()
            pack.assert_not_called()

    def test_repack_keeps_compiled_artifacts(self):
        self.fixture()
        base = self.root / "base.cpio.gz"
        base.write_bytes(b"base")
        build.manifest(base, compiler_version="test GCC")
        (self.root / "tests/pmp-virt/check-host.sh").write_bytes(b"script update")
        image = build.WORK / "out/linux-host/arch/riscv/boot/Image"
        before = build.digest(image)
        with patch.object(build, "validate_rootfs"), patch.object(build, "package_rootfs"):
            build.repack()
        self.assertEqual(before, build.digest(image))

    def test_generated_header_does_not_modify_firmware_source(self):
        source = self.root / "repo/opensbi"
        (source / "include/sbi").mkdir(parents=True)
        wrapper = source / "include/sbi/pmp_virt_layout.h"
        wrapper.write_bytes(b"#include PMP_VIRT_LAYOUT_HEADER\n")
        host = build.WORK / "out/linux-host"
        (host / "arch/riscv/boot").mkdir(parents=True)
        (host / "arch/riscv/boot/Image").write_bytes(self.image.read_bytes())
        (host / "System.map").write_bytes(self.system_map.read_bytes())
        config = build.WORK / "out/opensbi/platform/generic/kconfig/.config"
        config.parent.mkdir(parents=True)
        config.write_text("CONFIG_PMP_VIRT_SEAL=y\n")
        with patch.object(build, "verify_source", return_value=source), patch.object(build, "run") as commands:
            build.build_firmware("riscv64-linux-", 2)
        self.assertEqual(wrapper.read_bytes(), b"#include PMP_VIRT_LAYOUT_HEADER\n")
        self.assertTrue((build.WORK / "generated/pmp_virt_layout.h").is_file())
        self.assertIn(f"PMP_VIRT_LAYOUT_HEADER={(build.WORK / 'generated/pmp_virt_layout.h').as_posix()}", commands.call_args.args[0])

    def test_explicit_broken_compiler_does_not_fallback(self):
        with patch.dict(os.environ, {"CROSS_COMPILE": "chosen-"}), patch.object(build, "probe_toolchain", side_effect=RuntimeError("broken")) as probe:
            with self.assertRaisesRegex(RuntimeError, "Explicit"):
                build.cross_prefix()
            probe.assert_called_once_with("chosen-")

    def test_buildroot_automatic_fallback(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(build, "probe_toolchain", side_effect=[RuntimeError("broken"), "working-"]):
            self.assertEqual(build.cross_prefix(), "working-")

    def test_real_git_submodule_check_and_dirty_rejection(self):
        git(self.root, "init", "-q")
        git(self.root, "config", "user.name", "test")
        git(self.root, "config", "user.email", "test@example.invalid")
        source = self.root / "repo/qemu"
        source.mkdir(parents=True)
        git(source, "init", "-q")
        git(source, "config", "user.name", "test")
        git(source, "config", "user.email", "test@example.invalid")
        (source / "pmp.c").write_bytes(b"source\n")
        git(source, "add", "pmp.c")
        git(source, "commit", "-qm", "base")
        revision = git(source, "rev-parse", "HEAD")
        git(self.root, "update-index", "--add", "--cacheinfo", f"160000,{revision},repo/qemu")
        with patch.dict(build.SOURCES, {"qemu": {"path": "repo/qemu", "revision": revision}}):
            self.assertEqual(build.checked_submodule("qemu"), source)
            self.assertEqual(build.prepare_source("qemu"), source)
            (source / "pmp.c").write_bytes(b"changed\n")
            with self.assertRaisesRegex(RuntimeError, "local changes"):
                build.checked_submodule("qemu")

    def test_source_lock_separates_host_and_guest(self):
        self.assertNotEqual(build.SOURCES["linux-host"]["revision"], build.SOURCES["linux-guest"]["revision"])
        source = (ROOT / "scripts/virt-kvm.py").read_text()
        self.assertNotIn('"apply"', source)
        self.assertNotIn("adapt_firmware", source)
        self.assertNotIn("pmp-virt/patches", source)

    def test_runtime_parser_accepts_nested_serial_carriage_returns(self):
        lines = ["PMP.Virt SEALED:", "VIRT-KVM GUEST BOOTED", *regression.STEPS]
        transcript = "".join(line + ("\r\r\n" if "GUEST PASS" in line or "GUEST SHUTDOWN" in line else "\r\n") for line in lines)
        regression.check_transcript(transcript)
        for marker in regression.STEPS:
            with self.subTest(marker=marker), self.assertRaises(RuntimeError):
                regression.check_transcript(transcript.replace(marker, "# echo '" + marker + "'"))
        with self.assertRaises(RuntimeError):
            regression.check_transcript(transcript + "VIRT-REGRESSION FAIL guest checks\r\r\n")

    def test_runtime_parser_rejects_echoed_or_missing_results(self):
        valid = "PMP.Virt SEALED:\nVIRT-KVM GUEST BOOTED\n" + "\n".join(regression.STEPS) + "\n"
        regression.check_transcript(valid)
        for invalid in (valid.replace(regression.STEPS[1], "# echo '" + regression.STEPS[1] + "'"),
                        valid.replace(regression.STEPS[3], ""),
                        valid + "PMP.Virt TEST FAIL\n"):
            with self.assertRaises(RuntimeError):
                regression.check_transcript(invalid)


if __name__ == "__main__":
    unittest.main()
