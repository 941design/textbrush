"""Desktop dispatch forwards a process contract without starting inference."""

import json
import sys
from unittest.mock import patch

import pytest

from textbrush.cli import main
from textbrush.desktop import desktop_executable


@pytest.mark.parametrize("status", [0, 1, 7])
def test_desktop_process_options_output_and_status(tmp_path, monkeypatch, capfd, status):
    native = tmp_path / "native app"
    record = tmp_path / "record.json"
    native.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        f"with open({str(record)!r}, 'w') as f:\n"
        " json.dump({'argv': sys.argv[1:], 'env': {k: v for k, v in os.environ.items() "
        "if k in ['TEXTBRUSH_CONFIG_PATH', 'TEXTBRUSH_OUTPUT_FORMAT', "
        "'TEXTBRUSH_LOGGING_VERBOSITY', 'TEXTBRUSH_PYTHON']}}, f)\n"
        "print('desktop diagnostic', file=sys.stderr)\n"
        + ("print('/accepted/one.png\\n/accepted/two.png')\n" if status == 0 else "")
        + f"sys.exit({status})\n"
    )
    native.chmod(0o755)
    monkeypatch.setenv("TEXTBRUSH_DESKTOP", str(native))
    monkeypatch.delenv("TEXTBRUSH_DESKTOP_DISPATCH", raising=False)
    monkeypatch.delenv("TEXTBRUSH_PYTHON", raising=False)
    config = tmp_path / "custom.toml"
    config.write_text('[model]\nbuffer_size = 3\n[output]\nformat = "png"\n')
    reference = tmp_path / "reference image.png"
    reference.write_bytes(b"not decoded by CLI")
    output = tmp_path / "output image.jpg"
    with (
        patch("textbrush.backend.TextbrushBackend") as backend,
        patch("textbrush.cli.check_model_availability") as discovery,
        pytest.raises(SystemExit) as error,
    ):
        main(
            [
                "--prompt",
                "cat; $HOME",
                "--config",
                str(config),
                "--model",
                "flux2-klein-4b",
                "--reference",
                str(reference),
                "--reference",
                str(reference),
                "--preset",
                "portrait-medium",
                "--out",
                str(output),
                "--seed",
                "0",
                "--format",
                "jpg",
                "--verbose",
            ]
        )
    assert error.value.code == status
    backend.assert_not_called()
    discovery.assert_not_called()
    data = json.loads(record.read_text())
    assert data["argv"] == [
        "--prompt",
        "cat; $HOME",
        "--out",
        str(output),
        "--seed",
        "0",
        "--model",
        "flux2-klein-4b",
        "--preset",
        "portrait-medium",
        "--buffer-max",
        "3",
        "--reference",
        str(reference),
        "--reference",
        str(reference),
    ]
    assert data["env"]["TEXTBRUSH_CONFIG_PATH"] == str(config)
    assert data["env"]["TEXTBRUSH_OUTPUT_FORMAT"] == "jpg"
    assert data["env"]["TEXTBRUSH_LOGGING_VERBOSITY"] == "debug"
    assert data["env"]["TEXTBRUSH_PYTHON"] == sys.executable
    captured = capfd.readouterr()
    assert captured.out == ("/accepted/one.png\n/accepted/two.png\n" if status == 0 else "")
    assert captured.err == "desktop diagnostic\n"


def test_missing_native_and_recursive_override_fail_clearly(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TEXTBRUSH_DESKTOP", str(tmp_path / "missing"))
    monkeypatch.delenv("TEXTBRUSH_DESKTOP_DISPATCH", raising=False)
    monkeypatch.setattr("textbrush.cli.CONFIG_PATH", tmp_path / "config.toml")
    with pytest.raises(SystemExit) as error:
        main(["--prompt", "test"])
    assert error.value.code == 1
    assert "TEXTBRUSH_DESKTOP" in capsys.readouterr().err
    monkeypatch.setenv("TEXTBRUSH_DESKTOP_DISPATCH", "1")
    with pytest.raises(SystemExit) as error:
        main(["--prompt", "test"])
    assert error.value.code == 1
    assert "not the Python CLI" in capsys.readouterr().err


def test_explicit_native_selection_does_not_fallback(monkeypatch):
    monkeypatch.setenv("TEXTBRUSH_DESKTOP", "/chosen app/missing")
    assert desktop_executable() == "/chosen app/missing"
    monkeypatch.setenv("TEXTBRUSH_DESKTOP", "")
    with pytest.raises(ValueError, match="TEXTBRUSH_DESKTOP"):
        desktop_executable()


def test_sidecar_loads_custom_config_and_environment(tmp_path, monkeypatch):
    from textbrush.ipc.__main__ import main as sidecar_main

    config = tmp_path / "config.toml"
    config.write_text('[model]\nbuffer_size = 3\n[output]\nformat = "png"\n')
    monkeypatch.setenv("TEXTBRUSH_CONFIG_PATH", str(config))
    monkeypatch.setenv("TEXTBRUSH_OUTPUT_FORMAT", "jpg")
    with (
        patch("textbrush.ipc.__main__.MessageHandler") as handler,
        patch("textbrush.ipc.__main__.IPCServer") as server,
    ):
        sidecar_main()
    actual = handler.call_args.args[0]
    assert actual.model.buffer_size == 3
    assert actual.output.format == "jpg"
    server.return_value.run.assert_called_once()
    handler.return_value.shutdown.assert_called_once()


@pytest.mark.parametrize(
    "args",
    [["--auto-accept"], ["--auto-abort"], ["--preset", "portrait-small", "--aspect-ratio", "1:1"]],
)
def test_desktop_rejects_conflicting_options(args):
    with pytest.raises(SystemExit) as error:
        main(["--prompt", "test", *args])
    assert error.value.code == 2
