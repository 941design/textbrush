"""Check packaged fatal-startup shutdown on a real graphical session, without models.

Linux runners should invoke this under dbus-run-session and xvfb-run. The app's
own frontend timer closes the window; this probe does not simulate user input.
It checks exit/stdout/preview cleanup, not the rendered diagnostic text.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def check(app: Path, python: Path, report: Path, timeout: float) -> bool:
    report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="textbrush startup check ") as temporary:
        home = Path(temporary)
        previews = home / "previews"
        previews.mkdir()
        # Disable site-packages so the real bootstrap reliably encounters a
        # missing package, even when the runner itself has Textbrush installed.
        interpreter = home / "python without packages"
        interpreter.write_text(f'#!/bin/sh\nexec {shlex.quote(str(python))} -S "$@"\n')
        interpreter.chmod(0o700)
        environment = {
            name: os.environ[name]
            for name in ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS")
            if name in os.environ
        }
        environment.update(
            HOME=str(home),
            TMPDIR=str(previews),
            PATH="/usr/bin:/bin",
            TEXTBRUSH_PYTHON=str(interpreter),
            HF_HUB_OFFLINE="1",
        )
        started = time.monotonic()
        process = subprocess.Popen(
            [str(app)],
            cwd=home,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate()
        remaining = sorted(path.name for path in previews.glob("textbrush-preview-*"))
        passed = not timed_out and process.returncode == 1 and stdout == "" and not remaining
        result = {
            "app": str(app),
            "python": str(python),
            "scenario": "fatal missing-package error closes through frontend timer",
            "passed": passed,
            "timed_out": timed_out,
            "exit_code": process.returncode,
            "seconds": round(time.monotonic() - started, 3),
            "stdout": stdout,
            "stderr": stderr,
            "remaining_preview_directories": remaining,
        }
        report.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result), flush=True)
        return passed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    if os.name != "posix":
        parser.error("This check supports the macOS and Linux release targets")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    for path in (args.app, args.python):
        if not path.is_file() or not os.access(path, os.X_OK):
            parser.error(f"Not an executable file: {path}")
    raise SystemExit(
        0 if check(args.app.resolve(), args.python.absolute(), args.report, args.timeout) else 1
    )


if __name__ == "__main__":
    main()
