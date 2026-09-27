"""Check evidence collection with a subprocess fixture, without a desktop or model."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "installed_runtime_probe", Path(__file__).parents[1] / "scripts/check_installed_runtime.py"
)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


@pytest.mark.parametrize("mode", ["explicit", "default", "settings"])
def test_probe_preserves_logs_and_requires_clean_exit(tmp_path, mode):
    app = tmp_path / "app with spaces"
    app.write_text(
        f"#!{sys.executable}\n"
        "import os, pathlib, subprocess, sys, time\n"
        "home = pathlib.Path.home()\n"
        "assert str(home).startswith(os.environ['TMPDIR'].rsplit('/', 1)[0])\n"
        "assert not (home / '.cache/huggingface').exists()\n"
        "preview = pathlib.Path(os.environ['TMPDIR']) / 'textbrush-preview-fixture'\n"
        "preview.mkdir()\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
        "print('first log line', file=sys.stderr, flush=True)\n"
        "print('State changed: awaiting_model', file=sys.stderr, flush=True)\n"
        "time.sleep(.4)\n"
        "print('last log line', file=sys.stderr, flush=True)\n"
        "child.terminate()\n"
        "child.wait()\n"
        "preview.rmdir()\n"
        "sys.exit(1)\n"
    )
    app.chmod(0o700)
    report = tmp_path / "report.json"
    assert probe.check(app, Path(sys.executable), mode, report, timeout=5)
    result = json.loads(report.read_text())
    assert result["stderr"] == "first log line\nState changed: awaiting_model\nlast log line\n"
    assert result["remaining_child_pids"] == []
    assert result["remaining_preview_directories"] == []


def test_probe_does_not_pass_after_forced_cleanup(tmp_path):
    app = tmp_path / "hanging app"
    app.write_text(
        f"#!{sys.executable}\n"
        "import sys, time\n"
        "print('State changed: awaiting_model', file=sys.stderr, flush=True)\n"
        "time.sleep(30)\n"
    )
    app.chmod(0o700)
    report = tmp_path / "report.json"
    assert not probe.check(app, Path(sys.executable), "explicit", report, timeout=0.4)
    result = json.loads(report.read_text())
    assert result["initialized_through_frontend"]
    assert result["timed_out"]
    assert not result["passed"]
