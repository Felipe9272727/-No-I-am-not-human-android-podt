#!/usr/bin/env python3
"""Run a local Android emulator smoke test and preserve honest diagnostics.

Requires an installed Android SDK emulator, platform-tools, an AVD, and a
signed APK. Emulator and adb are started by this process so they share the
same loopback namespace. The script reports actual device execution only after
package installation and launcher start both succeed.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import time


def run(args: list[str], env: dict[str, str], timeout: int = 60, raw: bool = False) -> tuple[int, str | bytes]:
    result = subprocess.run(args, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=not raw, timeout=timeout)
    return result.returncode, result.stdout if raw else result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-root", type=Path, default=Path("tools/android/sdk"))
    parser.add_argument("--avd", default="ninah35")
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--package", default="org.reconstruction.port.preview")
    parser.add_argument("--timeout-seconds", type=int, default=360)
    parser.add_argument("--start-tap", nargs=2, type=int, metavar=("X", "Y"))
    parser.add_argument("--debug-skip-tap", nargs=2, type=int, metavar=("X", "Y"))
    parser.add_argument("--artifacts-dir", type=Path, default=Path("reconstruction/android-current/qa/android-emulator"))
    args = parser.parse_args()

    sdk = args.sdk_root.resolve()
    emulator = sdk / "emulator/emulator"
    adb = sdk / "platform-tools/adb"
    apk = args.apk.resolve()
    if not emulator.is_file() or not adb.is_file() or not apk.is_file():
        parser.error("SDK emulator, adb, or APK path is missing")
    args.artifacts_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["ANDROID_SDK_ROOT"] = str(sdk)
    env.setdefault("ANDROID_AVD_HOME", str(Path.home() / ".android/avd"))
    qemu_log = args.artifacts_dir / "emulator.log"
    adb_log = args.artifacts_dir / "adb.log"
    logcat_path = args.artifacts_dir / "logcat.txt"
    screenshot_path = args.artifacts_dir / "screen.png"
    report_path = args.artifacts_dir / "attempt.json"
    report = {
        "emulator_executed": False,
        "app_installed": False,
        "app_launched": False,
        "gameplay_frame_verified": False,
        "android_gles_gameplay_tested": False,
        "apk": str(apk),
        "avd": args.avd,
        "acceleration": "software CPU; SwiftShader GLES",
        "events": [],
    }
    started = time.monotonic()
    qemu_stream = qemu_log.open("w", encoding="utf-8")
    proc = None
    try:
        proc = subprocess.Popen(
            [str(emulator), "-avd", args.avd, "-no-window", "-no-audio", "-no-boot-anim",
             "-no-snapshot", "-gpu", "swiftshader_indirect", "-accel", "off", "-memory", "2048", "-cores", "2"],
            env=env, stdout=qemu_stream, stderr=subprocess.STDOUT,
        )
        report["emulator_executed"] = True
        report["events"].append({"event": "emulator_started", "pid": proc.pid, "elapsed_seconds": 0})
        code, output = run([str(adb), "start-server"], env)
        adb_log.write_text(output + "\n", encoding="utf-8")
        serial = None
        deadline = time.monotonic() + args.timeout_seconds
        while time.monotonic() < deadline and proc.poll() is None:
            _, listing = run([str(adb), "devices"], env)
            rows = [line.split() for line in listing.splitlines()[1:] if line.strip()]
            online = [row[0] for row in rows if len(row) > 1 and row[1] == "device" and row[0].startswith("emulator-")]
            if online:
                serial = online[0]
                report["events"].append({"event": "adb_device_online", "serial": serial,
                                         "elapsed_seconds": round(time.monotonic() - started)})
                break
            time.sleep(2)
        if not serial:
            report["failure"] = "adb_device_not_online_before_timeout_or_emulator_exit"
            report["elapsed_seconds"] = round(time.monotonic() - started)
            return write_report(report_path, report)

        booted = False
        while time.monotonic() < deadline and proc.poll() is None:
            _, value = run([str(adb), "-s", serial, "shell", "getprop", "sys.boot_completed"], env)
            if value == "1":
                booted = True
                report["events"].append({"event": "boot_completed_property", "elapsed_seconds": round(time.monotonic() - started)})
                break
            time.sleep(2)
        if not booted:
            report["failure"] = "android_boot_property_timeout"
            report["elapsed_seconds"] = round(time.monotonic() - started)
            return write_report(report_path, report)

        service_code, service_status = run([str(adb), "-s", serial, "shell", "service", "check", "package"], env)
        report["package_service"] = {"exit_code": service_code, "output": service_status}
        install_code, install_output = run([str(adb), "-s", serial, "install", "-r", "-t", str(apk)], env, timeout=900)
        report["install"] = {"exit_code": install_code, "output": install_output}
        report["app_installed"] = install_code == 0
        if install_code != 0:
            report["failure"] = "apk_install_failed"
        else:
            launch_code, launch_output = run([str(adb), "-s", serial, "shell", "monkey", "-p", args.package,
                                              "-c", "android.intent.category.LAUNCHER", "1"], env)
            report["launch"] = {"exit_code": launch_code, "output": launch_output}
            report["app_launched"] = launch_code == 0
            if launch_code == 0:
                if args.start_tap:
                    run([str(adb), "-s", serial, "shell", "input", "tap", *map(str, args.start_tap)], env)
                    time.sleep(5)
                if args.debug_skip_tap:
                    run([str(adb), "-s", serial, "shell", "input", "tap", *map(str, args.debug_skip_tap)], env)
                time.sleep(15)
                _, pixels = run([str(adb), "-s", serial, "exec-out", "screencap", "-p"], env, raw=True)
                screenshot_path.write_bytes(pixels)
                report["screenshot"] = str(screenshot_path)
                _, pid = run([str(adb), "-s", serial, "shell", "pidof", args.package], env)
                report["app_pid_after_launch"] = pid
                report["app_running_after_wait"] = bool(pid)
        _, logcat = run([str(adb), "-s", serial, "logcat", "-d", "-v", "threadtime", "-t", "2500"], env)
        logcat_path.write_text(logcat, encoding="utf-8")
        report["logcat"] = str(logcat_path)
        report["elapsed_seconds"] = round(time.monotonic() - started)
        return write_report(report_path, report)
    except (OSError, subprocess.TimeoutExpired) as error:
        report["failure"] = f"{type(error).__name__}: {error}"
        report["elapsed_seconds"] = round(time.monotonic() - started)
        return write_report(report_path, report)
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        qemu_stream.close()
        run([str(adb), "kill-server"], env, timeout=20)


def write_report(path: Path, report: dict) -> int:
    report.setdefault("elapsed_seconds", 0)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report.get("app_installed") and report.get("app_launched") else 2


if __name__ == "__main__":
    raise SystemExit(main())
