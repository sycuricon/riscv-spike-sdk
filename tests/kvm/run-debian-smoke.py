#!/usr/bin/env python3
"""Check Debian 13 user space on a temporary QEMU disk snapshot.

This intentionally boots init=/bin/sh; it does not test normal systemd login,
DHCP/DNS/apt or guest protection. The original disk receives no writes.
"""
import argparse
from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--disk", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    root = args.sdk.resolve()
    script = root / "scripts/kvm.py"
    spec = importlib.util.spec_from_file_location("sdk_build", script)
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    os.environ["DEBIAN_DISK"] = str(args.disk.resolve())
    with patch.object(build.os, "execv") as launch:
        build.launch(False)
        command = launch.call_args.args[1]
    for i, item in enumerate(command):
        if item == "-drive":
            command[i + 1] += ",snapshot=on"
    folder = build.WORK / "logs" / ("debian-smoke-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    folder.mkdir(parents=True)
    process = subprocess.Popen(command, cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, bufsize=0)
    chunks = queue.Queue()
    def pump():
        while True:
            data = process.stdout.read(4096)
            chunks.put(data)
            if not data:
                break
    threading.Thread(target=pump, daemon=True).start()
    check = "(test -c /dev/kvm || modprobe kvm) && test -c /dev/kvm"
    stage = 0
    transcript = ""
    started = time.monotonic()
    error = None
    def send(command):
        # Nested emulated UARTs have small FIFOs: pace even short commands.
        data = command.encode() + b"\n"
        for offset in range(0, len(data), 8):
            process.stdin.write(data[offset:offset + 8])
            process.stdin.flush()
            time.sleep(0.03)
    try:
        with (folder / "console.log").open("wb") as log:
            while time.monotonic() - started < args.timeout:
                try:
                    data = chunks.get(timeout=0.5)
                except queue.Empty:
                    continue
                if not data:
                    raise RuntimeError("QEMU exited before completion")
                log.write(data)
                log.flush()
                transcript += data.decode(errors="replace")
                if "Kernel panic" in transcript:
                    raise RuntimeError("Kernel/host failure in transcript")
                if stage == 0 and re.search(r"login:\s*$", transcript):
                    send("root")
                    stage = 1
                elif stage == 1 and re.search(r"[\r\n]#\s*$", transcript):
                    send(check + " && echo DEBIAN-SMOKE-HOST-BEFORE-PASS")
                    stage = 2
                elif stage == 2 and re.search(r"(?m)^DEBIAN-SMOKE-HOST-BEFORE-PASS\r*$", transcript):
                    send('/usr/bin/lkvm run --name debian-smoke -k /opt/guest/Image -d /dev/vda -m 768 -c 1 --console serial -n mode=none -p "console=ttyS0 root=/dev/vda1 rw rootwait maxcpus=1 init=/bin/sh"')
                    stage = 3
                elif stage == 3 and re.search(r"Run /bin/sh as init process", transcript) and re.search(r"[\r\n]#\s*$", transcript):
                    send('mount -t proc proc /proc; . /etc/os-release; test "$ID" = debian && test "$VERSION_ID" = 13 && echo DEBIAN-SMOKE-OS-PASS')
                    stage = 4
                elif stage == 4 and re.search(r"(?m)^DEBIAN-SMOKE-OS-PASS\r*$", transcript):
                    send('mount -t tmpfs tmpfs /tmp; test "$(uname -m)" = riscv64 && echo DEBIAN-SMOKE-ARCH-PASS')
                    stage = 5
                elif stage == 5 and re.search(r"(?m)^DEBIAN-SMOKE-ARCH-PASS\r*$", transcript):
                    send('echo debian-syscall-smoke > /tmp/sdk-smoke; test "$(cat /tmp/sdk-smoke)" = debian-syscall-smoke && echo DEBIAN-SMOKE-IO-PASS')
                    stage = 6
                elif stage == 6 and re.search(r"(?m)^DEBIAN-SMOKE-IO-PASS\r*$", transcript):
                    send('/usr/bin/true && sleep 1 && echo DEBIAN-SMOKE-USERSPACE-PASS; sync; /sbin/poweroff -ff')
                    stage = 7
                elif stage == 7 and re.search(r"(?m)^DEBIAN-SMOKE-USERSPACE-PASS\r*$", transcript) and "guest init failed" not in transcript and "Powering off" in transcript and re.search(r"[\r\n]#\s*$", transcript):
                    send(check + " && echo DEBIAN-SMOKE-HOST-AFTER-PASS")
                    stage = 8
                elif stage == 8 and re.search(r"(?m)^DEBIAN-SMOKE-HOST-AFTER-PASS\r*$", transcript):
                    process.stdin.write(b"\x01x")
                    process.stdin.flush()
                    process.wait(timeout=15)
                    if process.returncode:
                        raise RuntimeError(f"QEMU exited with {process.returncode}")
                    stage = 9
                    break
            if stage != 9:
                raise RuntimeError(f"Timeout in stage {stage}")
    except Exception as caught:
        error = str(caught)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        state = {"status":"PASS" if stage == 9 else "FAIL", "error":error,
                 "scope":"Debian 13 init=/bin/sh user-space smoke, disk snapshot, host before/after; no systemd/network/apt test",
                 "disk":str(args.disk.resolve()), "disk_write_mode":"QEMU snapshot=on",
                 "sdk_commit":subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip(),
                 "elapsed_seconds":round(time.monotonic()-started,2)}
        (folder / "result.json").write_text(json.dumps(state,indent=2)+"\n")
        (folder / "SHA256SUMS").write_text("".join(f"{build.digest(folder / name)}  {name}\n" for name in ("console.log","result.json")))
    print(json.dumps(state,indent=2))
    print("Evidence:",folder)
    return 0 if stage == 9 else 1


if __name__ == "__main__":
    sys.exit(main())
