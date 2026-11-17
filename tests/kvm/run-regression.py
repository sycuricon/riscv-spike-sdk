#!/usr/bin/env python3
"""Run the built images through a ordinary-host / ordinary-guest regression."""
import argparse
from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("kvm_build", ROOT / "scripts/kvm.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
STEPS = (
    "KVM-REGRESSION HOST BEFORE PASS",
    "KVM-REGRESSION GUEST PASS",
    "KVM-REGRESSION GUEST SHUTDOWN",
    "KVM-REGRESSION GUEST RETURNED",
    "KVM-REGRESSION HOST AFTER PASS",
    "KVM-REGRESSION ALL PASS",
)


def check_transcript(text):
    if re.search(r"KVM-REGRESSION FAIL|Kernel panic", text):
        raise RuntimeError("Failure marker in the runtime transcript")
    position = 0
    for marker in STEPS:
        found = re.search(r"(?m)^" + re.escape(marker) + r"\r*$", text[position:])
        if not found:
            raise RuntimeError(f"Missing or out-of-order runtime result: {marker}")
        position += found.end()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    if args.timeout < 1:
        parser.error("timeout must be positive")
    if sys.platform != "linux":
        parser.error("Run the runtime regression in the Ubuntu server terminal")
    if os.environ.get("DEBIAN_DISK"):
        parser.error("Unset DEBIAN_DISK; this suite runs the diskless Buildroot guest")
    build.require_checkout()
    build.verify()
    for name in build.SOURCES:
        build.source(name)
    folder = build.WORK / "logs" / ("regression-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    folder.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(build.WORK / "manifest.json", folder / "manifest.json")
    process = subprocess.Popen([sys.executable, "-u", str(ROOT / "scripts/kvm.py"), "run"],
                               cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, bufsize=0)
    chunks = queue.Queue()

    def pump():
        try:
            while True:
                data = process.stdout.read(4096)
                if not data:
                    break
                chunks.put(data)
        finally:
            chunks.put(None)

    threading.Thread(target=pump, daemon=True).start()
    started = time.monotonic()
    transcript = ""
    logged_in = False
    launched = False
    passed = False
    error = None
    try:
        with (folder / "console.log").open("wb") as log:
            while time.monotonic() - started < args.timeout:
                try:
                    data = chunks.get(timeout=0.5)
                except queue.Empty:
                    continue
                if data is None:
                    raise RuntimeError("QEMU exited before regression completion")
                log.write(data)
                log.flush()
                text = data.decode("utf-8", errors="replace")
                sys.stdout.write(text)
                sys.stdout.flush()
                transcript += text
                if re.search(r"KVM-REGRESSION FAIL|Kernel panic", transcript):
                    raise RuntimeError("Guest or host emitted a failure marker")
                if not logged_in and re.search(r"login:\s*$", transcript):
                    process.stdin.write(b"root\n")
                    process.stdin.flush()
                    logged_in = True
                    transcript += "\n[runner sent host login]\n"
                elif logged_in and not launched and re.search(r"(?:^|[\r\n])#\s*$", transcript):
                    process.stdin.write(b"/usr/bin/test-kvm-all\n")
                    process.stdin.flush()
                    launched = True
                if re.search(r"(?m)^KVM-REGRESSION ALL PASS\r*$", transcript):
                    check_transcript(transcript)
                    process.stdin.write(b"\x01x")
                    process.stdin.flush()
                    process.wait(timeout=15)
                    if process.returncode != 0:
                        raise RuntimeError(f"QEMU exited with status {process.returncode}")
                    passed = True
                    break
            else:
                raise RuntimeError(f"Runtime regression timed out after {args.timeout} seconds")
    except (Exception, KeyboardInterrupt) as caught:
        error = str(caught) or "Interrupted"
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        result = {"status": "PASS" if passed else "FAIL", "error": error,
                  "scope": "upstream host, diskless Buildroot guest, guest shutdown and host return",
                  "sdk_commit": build.output(["git", "-C", ROOT, "rev-parse", "HEAD"]),
                  "sdk_status": build.output(["git", "-C", ROOT, "status", "--porcelain"]),
                  "elapsed_seconds": round(time.monotonic() - started, 2)}
        (folder / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        (folder / "SHA256SUMS").write_text("".join(
            f"{build.digest(folder / name)}  {name}\n" for name in ("console.log", "manifest.json", "result.json")))
    print(f"\nRuntime {'PASS' if passed else 'FAIL'}; evidence: {folder}")
    if not passed:
        raise RuntimeError(error)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(f"STOP: {error}", file=sys.stderr)
        sys.exit(1)
