"""Shared path constants for the textbrush project."""

from pathlib import Path

# Project root (parent of textbrush package)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# XDG-compliant config path
CONFIG_DIR = Path.home() / ".config" / "textbrush"
CONFIG_PATH = CONFIG_DIR / "config.toml"

# Default output paths (user-facing, configured via config file)
DEFAULT_OUTPUT_DIR = Path.home() / "Pictures" / "textbrush"


def display_path(path: Path | str) -> str:
    """Convert path to display string with home directory replaced by tilde.

    Args:
        path: Path object or string path to convert

    Returns:
        String path with user home directory replaced by ~
    """
    path_str = str(path)
    home = str(Path.home())
    # Check for exact match or match followed by path separator
    if path_str == home:
        return "~"
    if path_str.startswith(home + "/"):
        return "~" + path_str[len(home) :]
    return path_str
