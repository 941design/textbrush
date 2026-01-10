"""Tests for textbrush.paths module."""

from pathlib import Path
from unittest.mock import patch

from textbrush.paths import display_path


class TestDisplayPath:
    """Tests for display_path function."""

    def test_replaces_home_directory_with_tilde(self):
        """Home directory is replaced with ~."""
        with patch.object(Path, "home", return_value=Path("/Users/testuser")):
            result = display_path("/Users/testuser/Pictures/image.png")
            assert result == "~/Pictures/image.png"

    def test_handles_path_object(self):
        """Works with Path objects."""
        with patch.object(Path, "home", return_value=Path("/Users/testuser")):
            result = display_path(Path("/Users/testuser/Pictures/image.png"))
            assert result == "~/Pictures/image.png"

    def test_returns_unchanged_when_not_in_home(self):
        """Returns unchanged path when not under home directory."""
        with patch.object(Path, "home", return_value=Path("/Users/testuser")):
            result = display_path("/tmp/image.png")
            assert result == "/tmp/image.png"

    def test_returns_unchanged_for_partial_match(self):
        """Returns unchanged when path only partially matches home."""
        with patch.object(Path, "home", return_value=Path("/Users/test")):
            result = display_path("/Users/testuser/image.png")
            assert result == "/Users/testuser/image.png"

    def test_handles_exact_home_path(self):
        """Handles path that is exactly the home directory."""
        with patch.object(Path, "home", return_value=Path("/Users/testuser")):
            result = display_path("/Users/testuser")
            assert result == "~"

    def test_handles_home_with_trailing_content(self):
        """Handles paths that start with home but have additional segments."""
        with patch.object(Path, "home", return_value=Path("/home/user")):
            result = display_path("/home/user/deeply/nested/file.txt")
            assert result == "~/deeply/nested/file.txt"
