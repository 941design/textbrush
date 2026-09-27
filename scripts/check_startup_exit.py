"""Check packaged fatal-startup shutdown on a real graphical session, without models.

Linux runners should invoke this under dbus-run-session and xvfb-run. The app's
own frontend timer closes the window; this probe does not simulate user input.
It checks the actual bootstrap diagnostic, exit/stdout/preview cleanup, not the
rendered diagnostic text. Missing executables use the retry screen and require
the separate operator-driven native-close check.
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


def check(
    app: Path, python: Path, report: Path, timeout: float, scenario: str = "missing-package"
) -> bool:
    version = json.loads(
        subprocess.check_output(
            [
                str(python),
                "-I",
                "-S",
                "-c",
                "import json, sys; print(json.dumps(list(sys.version_info[:3])))",
            ],
            text=True,
        )
    )
    if scenario == "unsupported-python" and version[:2] >= [3, 11]:
        raise ValueError("unsupported-python requires an actual Python older than 3.11")
    if scenario == "missing-package" and version[:2] < [3, 11]:
        raise ValueError(
            "missing-package requires Python 3.11+ so the version guard does not mask it"
        )
    report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="textbrush startup check ") as temporary:
        home = Path(temporary)
        previews = home / "previews"
        previews.mkdir()
        protocol = home / "bootstrap messages.jsonl"
        interpreter = home / "python runtime with spaces"
        # Disable packages; the real bootstrap's version check precedes
        # imports when an actual unsupported Python is selected.
        # Forward unmodified IPC bytes while retaining the actual diagnostic.
        # pipefail preserves Python's exit status instead of tee's success.
        interpreter.write_text(
            "#!/bin/bash\nset -o pipefail\n"
            f'{shlex.quote(str(python))} -S "$@" | /usr/bin/tee {shlex.quote(str(protocol))}\n'
        )
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
        messages = []
        if protocol.exists():
            for line in protocol.read_text().splitlines():
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    messages.append({"invalid_json": line})
        expected = (
            "Python 3.11 or newer"
            if scenario == "unsupported-python"
            else "Install textbrush[model]"
        )
        diagnostic_seen = any(
            isinstance(message, dict)
            and message.get("type") == "error"
            and isinstance(payload := message.get("payload"), dict)
            and payload.get("fatal") is True
            and payload.get("operation") == "startup"
            and expected in payload.get("message", "")
            for message in messages
        )
        passed = (
            diagnostic_seen
            and not timed_out
            and process.returncode == 1
            and stdout == ""
            and not remaining
        )
        result = {
            "app": str(app),
            "python": str(python),
            "scenario": scenario,
            "python_version": version,
            "bootstrap_messages": messages,
            "expected_diagnostic_seen": diagnostic_seen,
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
    parser.add_argument(
        "--scenario",
        default="missing-package",
        choices=("missing-package", "unsupported-python"),
    )
    args = parser.parse_args()
    if os.name != "posix":
        parser.error("This check supports the macOS and Linux release targets")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    for path in (args.app, args.python):
        if not path.is_file() or not os.access(path, os.X_OK):
            parser.error(f"Not an executable file: {path}")
    raise SystemExit(
        0
        if check(
            args.app.resolve(), args.python.absolute(), args.report, args.timeout, args.scenario
        )
        else 1
    )


if __name__ == "__main__":
    main()
