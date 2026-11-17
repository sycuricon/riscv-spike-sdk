import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import json

ROOT = Path(__file__).resolve().parents[2]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
build = load("kvm_build", ROOT / "scripts/kvm.py")
regression = load("kvm_regression", ROOT / "tests/kvm/run-regression.py")

class Checks(unittest.TestCase):
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
