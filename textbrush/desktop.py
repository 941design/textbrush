"""Launch the installed native desktop without loading an inference backend."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def desktop_executable() -> str:
    """Resolve a native installation without invoking the Python console script."""
    explicit = os.environ.get("TEXTBRUSH_DESKTOP")
    if explicit is not None:
        if not explicit:
            raise ValueError("TEXTBRUSH_DESKTOP must name the native desktop executable")
        return explicit
    candidates = [
        Path("/Applications/Textbrush.app/Contents/MacOS/textbrush"),
        Path.home() / "Applications/Textbrush.app/Contents/MacOS/textbrush",
        Path("/usr/bin/textbrush"),
        Path("/usr/local/bin/textbrush"),
    ]
    named = shutil.which("textbrush-desktop")
    if named:
        candidates.insert(0, Path(named))
    launcher = Path(sys.argv[0]).resolve()
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            if candidate.resolve() != launcher:
                return str(candidate)
    raise FileNotFoundError(
        "Install the Textbrush desktop app and set TEXTBRUSH_DESKTOP to its executable, "
        "or use --headless for command-line generation."
    )


def run_desktop(args, config, config_path: Path) -> None:
    """Forward native options and CLI configuration; inherit stdout/stderr verbatim."""
    if os.environ.get("TEXTBRUSH_DESKTOP_DISPATCH"):
        raise ValueError("TEXTBRUSH_DESKTOP must point to the native app, not the Python CLI")
    command = [desktop_executable(), "--prompt", args.prompt]
    for option, value in [
        ("--out", args.out),
        ("--seed", args.seed),
        ("--aspect-ratio", args.aspect_ratio),
        ("--model", args.model),
        ("--preset", args.preset),
        ("--buffer-max", config.model.buffer_size),
    ]:
        if value is not None:
            command.extend([option, str(value)])
    for reference in args.reference:
        command.extend(["--reference", str(reference.expanduser().resolve())])
    env = os.environ.copy()
    env["TEXTBRUSH_DESKTOP_DISPATCH"] = "1"
    # The native app's sidecar loads the same config file with normal environment
    # precedence; only explicit CLI overrides become child-environment overrides.
    env["TEXTBRUSH_CONFIG_PATH"] = str(config_path.expanduser().resolve())
    if args.format is not None:
        env["TEXTBRUSH_OUTPUT_FORMAT"] = args.format
    if args.verbose:
        env["TEXTBRUSH_LOGGING_VERBOSITY"] = "debug"
    env.setdefault("TEXTBRUSH_PYTHON", sys.executable)
    try:
        code = subprocess.call(command, env=env)
    except OSError as error:
        raise RuntimeError(
            f"Cannot launch Textbrush desktop: {error}. "
            "Set TEXTBRUSH_DESKTOP to the installed native executable."
        ) from error
    raise SystemExit(code if code >= 0 else 128 - code)
