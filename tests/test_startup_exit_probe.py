"""Validate diagnostic evidence transport without launching a GUI or models."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "startup_exit_probe", Path(__file__).parents[1] / "scripts/check_startup_exit.py"
)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def test_probe_captures_diagnostic_and_preserves_interpreter_failure(tmp_path):
    app = tmp_path / "app with spaces"
    message = {
        "type": "error",
        "payload": {"fatal": True, "operation": "startup", "message": "Install textbrush[model]"},
    }
    bootstrap = f"import json; print(json.dumps({message!r}), flush=True); raise SystemExit(1)"
    app.write_text(
        f"#!{sys.executable}\n"
        "import os, subprocess, sys\n"
        f"result = subprocess.run([os.environ['TEXTBRUSH_PYTHON'], '-I', '-c', {bootstrap!r}], "
        "stdout=subprocess.PIPE, text=True)\n"
        f"assert result.stdout == {json.dumps(message) + chr(10)!r}\n"
        "sys.exit(result.returncode)\n"
    )
    app.chmod(0o700)
    report = tmp_path / "report.json"
    assert probe.check(app, Path(sys.executable), report, 5)
    result = json.loads(report.read_text())
    assert result["bootstrap_messages"] == [message]
    assert result["expected_diagnostic_seen"]
    assert result["exit_code"] == 1


def test_exit_one_alone_is_not_evidence_of_expected_startup_failure(tmp_path):
    app = tmp_path / "unrelated failure"
    app.write_text("#!/bin/sh\nexit 1\n")
    app.chmod(0o700)
    report = tmp_path / "report.json"
    assert not probe.check(app, Path(sys.executable), report, 5)
    result = json.loads(report.read_text())
    assert result["exit_code"] == 1
    assert not result["expected_diagnostic_seen"]


def test_unsupported_scenario_requires_an_actual_older_interpreter(tmp_path):
    with pytest.raises(ValueError, match="actual Python older than 3.11"):
        probe.check(
            tmp_path / "app", Path(sys.executable), tmp_path / "report", 5, "unsupported-python"
        )
