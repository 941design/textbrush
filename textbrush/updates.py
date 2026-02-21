"""Update check module for textbrush.

Provides manual update checking against the GitHub Releases API.
No automatic checks — user must explicitly invoke --check-updates.
No telemetry or data collection beyond the read-only API request.
"""

from __future__ import annotations

import json
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from typing import Literal

GITHUB_API_URL = "https://api.github.com/repos/941design/textbrush/releases/latest"
GITHUB_RELEASES_URL = "https://github.com/941design/textbrush/releases"
REQUEST_TIMEOUT = 5  # seconds


def get_current_version() -> str:
    """Read the current textbrush version from pyproject.toml.

    CONTRACT:
      Outputs:
        - str: semantic version string (e.g. "0.1.0")

      Invariants:
        - Reads pyproject.toml from package root (two levels up from this file)
        - Returns [project].version field
        - Raises FileNotFoundError if pyproject.toml not found
        - Raises KeyError if version field missing

    Algorithm:
      1. Locate pyproject.toml relative to this module's directory
      2. Parse using tomllib (stdlib, Python 3.11+)
      3. Return project.version string
    """
    # This file is at textbrush/updates.py; pyproject.toml is one level up
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


def get_latest_release(verbose: bool = False) -> dict:
    """Query the GitHub Releases API for the latest textbrush release.

    CONTRACT:
      Inputs:
        - verbose: if True, print debug info to stderr

      Outputs:
        - dict: parsed GitHub API response with at minimum:
          - tag_name: str (e.g. "v0.2.0")
          - html_url: str (release page URL)
          - assets: list of dicts with "name" and "browser_download_url"

      Raises:
        - urllib.error.URLError: on network errors
        - urllib.error.HTTPError: on HTTP errors (includes rate limit)
        - json.JSONDecodeError: on unexpected non-JSON response
        - ValueError: on missing expected fields in response

    Algorithm:
      1. Build request with User-Agent header for identification
      2. Send GET request with 5 second timeout
      3. Parse JSON response
      4. Validate tag_name field exists
      5. Return parsed response
    """
    current_version = _get_version_safe()
    user_agent = f"textbrush/{current_version}"

    req = urllib.request.Request(
        GITHUB_API_URL,
        headers={"User-Agent": user_agent, "Accept": "application/vnd.github+json"},
    )

    if verbose:
        print(f"Querying: {GITHUB_API_URL}", file=sys.stderr)

    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
        body = response.read()
        data = json.loads(body)

    if "tag_name" not in data:
        raise ValueError("Unexpected API response: missing 'tag_name' field")

    return data


def _get_version_safe() -> str:
    """Return current version, falling back to 'unknown' on any error."""
    try:
        return get_current_version()
    except Exception:
        return "unknown"


def compare_versions(current: str, latest: str) -> Literal["update", "current", "dev"]:
    """Compare current version with latest release version.

    CONTRACT:
      Inputs:
        - current: semantic version string (e.g. "0.1.0")
        - latest: semantic version string from GitHub tag (e.g. "0.2.0", strips "v" prefix)

      Outputs:
        - "update": latest > current (update available)
        - "current": latest == current (up to date)
        - "dev": current > latest (development version)

    Algorithm:
      1. Strip "v" prefix from latest if present
      2. Parse both with packaging.version.Version
      3. Compare and return appropriate label
    """
    from packaging.version import Version

    latest_clean = latest.lstrip("v")
    current_ver = Version(current)
    latest_ver = Version(latest_clean)

    if latest_ver > current_ver:
        return "update"
    elif latest_ver == current_ver:
        return "current"
    else:
        return "dev"


def _format_update_available(current: str, release: dict) -> str:
    """Format the update-available notification message.

    Uses the release data to list available asset download links.
    """
    tag = release.get("tag_name", "")
    html_url = release.get("html_url", f"{GITHUB_RELEASES_URL}/latest")
    assets = release.get("assets", [])
    latest_version = tag.lstrip("v")

    lines = [
        "Textbrush Update Available",
        "",
        f"  Current version: {current}",
        f"  Latest version:  {latest_version}",
        "",
        f"  Release notes: {html_url}",
    ]

    if assets:
        lines.append("")
        lines.append("  Download options:")
        for asset in assets:
            name = asset.get("name", "")
            url = asset.get("browser_download_url", "")
            if name and url:
                lines.append(f"    - {name}")
        lines.append("")
        lines.append(f"  Direct link: {GITHUB_RELEASES_URL}/latest")
    else:
        lines.append("")
        lines.append(f"  Direct link: {GITHUB_RELEASES_URL}/latest")

    lines.append("")
    lines.append("Update manually by downloading from GitHub Releases.")

    return "\n".join(lines)


def _format_up_to_date(version: str) -> str:
    """Format the up-to-date confirmation message."""
    tag = f"v{version}"
    return f"Textbrush is up to date ({tag})\n\nView releases: {GITHUB_RELEASES_URL}"


def _format_dev_version(current: str, latest_tag: str) -> str:
    """Format the development version notification message."""
    latest_version = latest_tag.lstrip("v")
    return (
        f"Running development version ({current})\n"
        f"\n"
        f"Latest stable release: {latest_version}\n"
        f"View releases: {GITHUB_RELEASES_URL}"
    )


def _format_network_error() -> str:
    """Format the network failure error message."""
    return (
        "Failed to check for updates: Network error\n"
        "Please check your internet connection and try again.\n"
        "\n"
        f"View releases manually: {GITHUB_RELEASES_URL}"
    )


def _format_rate_limit_error() -> str:
    """Format the GitHub API rate limit error message."""
    return (
        "Failed to check for updates: GitHub API rate limit exceeded\n"
        "Please wait a few minutes and try again.\n"
        "\n"
        f"View releases manually: {GITHUB_RELEASES_URL}"
    )


def _format_api_error() -> str:
    """Format the unexpected API response error message."""
    return (
        "Failed to check for updates: Unexpected API response\n"
        "Please try again later.\n"
        "\n"
        f"View releases manually: {GITHUB_RELEASES_URL}"
    )


def check_for_updates(verbose: bool = False) -> None:
    """Check for updates and print appropriate notification.

    Main entry point for the update check workflow. Always exits with code 0
    (update check is informational, not critical). Errors are reported as
    user-friendly messages rather than exceptions.

    CONTRACT:
      Inputs:
        - verbose: if True, print debug info to stderr

      Outputs:
        - None (side effects: prints to stdout, exits with code 0)

      Invariants:
        - Always exits with code 0
        - Prints exactly one notification block to stdout
        - On error: prints error message to stdout, exits 0
        - No data sent to GitHub (read-only API)
        - Single attempt, no retries
        - 5 second timeout on network request

    Algorithm:
      1. Get current version from pyproject.toml
      2. Query GitHub API for latest release
      3. Compare versions
      4. Print appropriate notification:
         - "update": update available with download links
         - "current": up to date confirmation
         - "dev": development version notice
      5. On any network/API error: print error message
      6. Exit with code 0 in all cases
    """
    try:
        current = get_current_version()
    except Exception as e:
        if verbose:
            print(f"Could not read current version: {e}", file=sys.stderr)
        current = "unknown"

    try:
        release = get_latest_release(verbose=verbose)
    except urllib.error.HTTPError as e:
        if e.code == 403 or e.code == 429:
            print(_format_rate_limit_error())
        else:
            print(_format_api_error())
        sys.exit(0)
    except urllib.error.URLError:
        print(_format_network_error())
        sys.exit(0)
    except (json.JSONDecodeError, ValueError, KeyError):
        print(_format_api_error())
        sys.exit(0)
    except Exception:
        print(_format_network_error())
        sys.exit(0)

    tag_name = release.get("tag_name", "")

    try:
        result = compare_versions(current, tag_name)
    except Exception:
        print(_format_api_error())
        sys.exit(0)

    if result == "update":
        print(_format_update_available(current, release))
    elif result == "current":
        print(_format_up_to_date(current))
    else:
        print(_format_dev_version(current, tag_name))

    sys.exit(0)
