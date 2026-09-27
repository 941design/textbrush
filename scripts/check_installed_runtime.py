"""Observe an installed app while an operator closes or aborts its native window.

Runs without model selection in a fresh profile, outside the checkout. This
probe never sends UI input; close/abort must be performed in the actual window.
Use a runtime containing the installed wheel and its declared model extra.
Linux requires an existing graphical/DBus session. Reports retain stderr and
temporary paths, but do not inherit credentials or the user's model cache.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path


def children(pid: int) -> set[int]:
    result = subprocess.run(
        ["ps", "-axo", "pid=,ppid="], check=True, capture_output=True, text=True
    )
    return {
        int(parts[0]) for row in result.stdout.splitlines() if (parts := row.split())[1] == str(pid)
    }


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def check(app: Path, python: Path, mode: str, report: Path, timeout: float) -> bool:
    with tempfile.TemporaryDirectory(prefix="textbrush installed check ") as temporary:
        profile = Path(temporary)
        previews = profile / "tmp"
        previews.mkdir()
        environment = {
            key: os.environ[key]
            for key in ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS")
            if key in os.environ
        }
        environment.update(
            HOME=str(profile),
            TMPDIR=str(previews),
            PATH="/usr/bin:/bin:/usr/sbin:/sbin",
            HF_HUB_OFFLINE="1",
            TEXTBRUSH_LOGGING_VERBOSITY="debug",
        )
        if mode == "explicit":
            environment["TEXTBRUSH_PYTHON"] = str(python)
        elif mode == "default":
            environment["PATH"] = str(python.parent) + ":" + environment["PATH"]
        else:
            settings = profile / ".config/textbrush/python-path"
            settings.parent.mkdir(parents=True)
            settings.write_text(str(python) + "\n")
        started = time.monotonic()
        observed_children: set[int] = set()
        observed_previews: set[Path] = set()
        initialized = False
        stdout_path = profile / "stdout"
        stderr_path = profile / "stderr"
        with stdout_path.open("w") as output, stderr_path.open("w") as errors:
            process = subprocess.Popen(
                [str(app)],
                cwd=profile,
                env=environment,
                stdout=output,
                stderr=errors,
                start_new_session=True,
            )
            try:
                while process.poll() is None and time.monotonic() - started < timeout:
                    observed_children.update(children(process.pid))
                    observed_previews.update(previews.glob("textbrush-preview-*"))
                    # Read through a separate descriptor: seeking the child's
                    # inherited descriptor would also change its write offset.
                    if (
                        not initialized
                        and "State changed: awaiting_model" in stderr_path.read_text()
                    ):
                        initialized = True
                        print(
                            "Initialized through frontend. Close or abort the native window now.",
                            flush=True,
                        )
                    time.sleep(0.1)
                timed_out = process.poll() is None
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
            deadline = time.monotonic() + 5
            while any(alive(pid) for pid in observed_children) and time.monotonic() < deadline:
                time.sleep(0.1)
            stdout = stdout_path.read_text()
            stderr = stderr_path.read_text()
        remaining_children = sorted(pid for pid in observed_children if alive(pid))
        remaining_previews = sorted(str(path) for path in previews.glob("textbrush-preview-*"))
        passed = (
            initialized
            and not timed_out
            and process.returncode == 1
            and stdout == ""
            and bool(observed_children)
            and bool(observed_previews)
            and not remaining_children
            and not remaining_previews
        )
        result = {
            "app": str(app),
            "python": str(python),
            "mode": mode,
            "passed": passed,
            "initialized_through_frontend": initialized,
            "timed_out": timed_out,
            "exit_code": process.returncode,
            "seconds": round(time.monotonic() - started, 3),
            "stdout": stdout,
            "stderr": stderr,
            "observed_child_pids": sorted(observed_children),
            "remaining_child_pids": remaining_children,
            "observed_preview_directories": sorted(map(str, observed_previews)),
            "remaining_preview_directories": remaining_previews,
            "limitations": (
                "Fresh profile on this host; operator supplies native close/abort. No inference."
            ),
        }
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result), flush=True)
        return passed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--mode", choices=("explicit", "default", "settings"), required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()
    for path in (args.app, args.python):
        if not path.is_file() or not os.access(path, os.X_OK):
            parser.error(f"Not an executable file: {path}")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    raise SystemExit(
        0
        if check(args.app.resolve(), args.python.absolute(), args.mode, args.report, args.timeout)
        else 1
    )


if __name__ == "__main__":
    main()
