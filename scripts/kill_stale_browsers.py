#!/usr/bin/env python3
"""
Cross-platform utility to kill stale Chrome and ChromeDriver processes.
Replicates scripts/kill_stale_browsers.ps1 behavior with ASCII-only output.
"""
from __future__ import annotations

import os
import sys
import time
from typing import Iterable


def _print_header() -> None:
    print("\n=========================================")
    print("  Stale Browser Process Killer")
    print("=========================================\n")


def _normalize_name(name: str) -> str:
    n = name.lower()
    if n.endswith(".exe"):
        n = n[:-4]
    return n


def _kill_with_psutil() -> tuple[int, int]:
    try:
        import psutil  # type: ignore
    except Exception:
        return (-1, -1)  # indicate psutil not available

    chrome_killed = 0
    driver_killed = 0

    targets = {"chrome", "chromedriver"}

    # Collect PIDs by target name
    chrome_pids: list[int] = []
    driver_pids: list[int] = []

    for p in psutil.process_iter(attrs=["pid", "name"]):
        try:
            name = p.info.get("name") or ""
            n = _normalize_name(name)
            if n == "chrome":
                chrome_pids.append(int(p.info["pid"]))
            elif n == "chromedriver":
                driver_pids.append(int(p.info["pid"]))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    # Terminate then kill remaining
    def terminate_group(pids: Iterable[int]) -> int:
        count = 0
        processes = []
        for pid in pids:
            try:
                processes.append(psutil.Process(pid))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        for proc in processes:
            try:
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        gone, alive = psutil.wait_procs(processes, timeout=2)
        count += len(gone)
        for proc in alive:
            try:
                proc.kill()
                count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return count

    print("Searching for Chrome processes...", flush=True)
    if chrome_pids:
        chrome_killed = terminate_group(chrome_pids)
        print(f"OK: Terminated {chrome_killed} Chrome process(es)")
    else:
        print("INFO: No Chrome processes found")

    print("Searching for ChromeDriver processes...", flush=True)
    if driver_pids:
        driver_killed = terminate_group(driver_pids)
        print(f"OK: Terminated {driver_killed} ChromeDriver process(es)")
    else:
        print("INFO: No ChromeDriver processes found")

    return (chrome_killed, driver_killed)


def _kill_with_system() -> tuple[int, int]:
    """Fallback using OS-native commands when psutil is unavailable."""
    import subprocess

    chrome_killed = 0
    driver_killed = 0

    if os.name == "nt":
        print("Searching for Chrome processes...", flush=True)
        try:
            # taskkill returns non-zero if no process found; we ignore the code
            res = subprocess.run(
                ["taskkill", "/F", "/IM", "chrome.exe", "/T"],
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                # best-effort: cannot easily count; report generic
                print("OK: Terminated Chrome process(es)")
                chrome_killed = 1
            else:
                print("INFO: No Chrome processes found")
        except Exception as e:
            print(f"WARN: Error checking Chrome processes: {e}")

        print("Searching for ChromeDriver processes...", flush=True)
        try:
            res = subprocess.run(
                ["taskkill", "/F", "/IM", "chromedriver.exe", "/T"],
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                print("OK: Terminated ChromeDriver process(es)")
                driver_killed = 1
            else:
                print("INFO: No ChromeDriver processes found")
        except Exception as e:
            print(f"WARN: Error checking ChromeDriver processes: {e}")

    else:
        print("Searching for Chrome processes...", flush=True)
        try:
            subprocess.run(["pkill", "-9", "-f", "chrome"], capture_output=True, text=True)
            print("OK: Terminated Chrome process(es)")
            chrome_killed = 1
        except Exception as e:
            print(f"INFO: No Chrome processes found ({e})")

        print("Searching for ChromeDriver processes...", flush=True)
        try:
            subprocess.run(["pkill", "-9", "-f", "chromedriver"], capture_output=True, text=True)
            print("OK: Terminated ChromeDriver process(es)")
            driver_killed = 1
        except Exception as e:
            print(f"INFO: No ChromeDriver processes found ({e})")

    return (chrome_killed, driver_killed)


def main() -> int:
    _print_header()

    # Prefer psutil for accuracy; fall back to system tools
    chrome_killed, driver_killed = _kill_with_psutil()
    if chrome_killed == -1 and driver_killed == -1:
        chrome_killed, driver_killed = _kill_with_system()

    total = max(0, chrome_killed) + max(0, driver_killed)

    print("\n=========================================")
    if total > 0:
        print(f"OK: Successfully terminated {total} process(es)")
        print(f"   - Chrome: {max(0, chrome_killed)}")
        print(f"   - ChromeDriver: {max(0, driver_killed)}")
    else:
        print("OK: No stale browser processes found")
    print("=========================================\n")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nAborted by user.")
        sys.exit(130)
