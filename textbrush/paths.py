"""Shared path constants for the textbrush project."""

from pathlib import Path

# Project root (parent of textbrush package)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# XDG-compliant config path
CONFIG_DIR = Path.home() / ".config" / "textbrush"
CONFIG_PATH = CONFIG_DIR / "config.toml"

# Default output paths (user-facing, configured via config file)
DEFAULT_OUTPUT_DIR = Path.home() / "Pictures" / "textbrush"
