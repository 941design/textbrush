# Feature Specification: Manual Update Check

**Status:** Planned (Not Implemented)
**Priority:** Low
**Target Version:** TBD

## Problem Statement

Users have no way to discover new textbrush releases without manually checking the GitHub repository. This leads to:

- Running outdated versions with potential bugs or missing features
- Lack of awareness about available updates
- Manual, error-prone update process

A lightweight, privacy-respecting update check mechanism would improve user experience without requiring auto-update infrastructure.

## Core Functionality

Provide a user-triggered update check that:
1. Queries GitHub Releases API for the latest version
2. Compares with current installed version
3. Displays notification if newer version available
4. Provides download link to GitHub Releases
5. Respects user privacy (manual trigger only, no telemetry)

## Functional Requirements

### FR1: CLI Flag for Update Check

**Requirement:** Add `--check-updates` flag to CLI

**Behavior:**
- Flag is optional, no value required
- When present, checks for updates and exits
- Cannot be combined with `--prompt`, `--download-model`, or `--headless`
- Exits with code 0 on success (regardless of update availability)

**Validation:**
- Conflicts with `--prompt`: Error "Cannot use --check-updates with --prompt"
- Conflicts with `--download-model`: Error "Cannot use --check-updates with --download-model"
- Conflicts with `--headless`: Error "Cannot use --check-updates with --headless"

### FR2: Version Comparison

**Requirement:** Compare current version with latest GitHub release

**Current Version Detection:**
- Read from `pyproject.toml` `[project] version` field
- Parse semantic version: `MAJOR.MINOR.PATCH` (e.g., `0.1.0`)

**Latest Version Detection:**
- Query GitHub API: `GET https://api.github.com/repos/941design/textbrush/releases/latest`
- Parse response JSON: `tag_name` field (format: `v0.2.0`)
- Strip `v` prefix for comparison

**Comparison Logic:**
```python
from packaging.version import Version

current = Version("0.1.0")
latest = Version("0.2.0")  # from tag_name="v0.2.0"

if latest > current:
    print("Update available")
elif latest == current:
    print("Up to date")
else:
    print("Running development version")  # current > latest
```

### FR3: Update Available Notification

**Requirement:** Display clear notification when update is available

**Output Format:**
```
Textbrush Update Available

  Current version: 0.1.0
  Latest version:  0.2.0

  Release notes: https://github.com/941design/textbrush/releases/tag/v0.2.0

  Download options:
    - macOS (Apple Silicon): textbrush-aarch64-apple-darwin.tar.gz
    - macOS (Intel):         textbrush-x86_64-apple-darwin.tar.gz
    - Linux (x86_64):        textbrush-x86_64-unknown-linux-gnu.tar.gz

  Direct link: https://github.com/941design/textbrush/releases/latest

Update manually by downloading from GitHub Releases.
```

### FR4: Up-to-Date Notification

**Requirement:** Display confirmation when already on latest version

**Output Format:**
```
Textbrush is up to date (v0.2.0)

View releases: https://github.com/941design/textbrush/releases
```

### FR5: Development Version Notification

**Requirement:** Handle case where current version > latest release

**Scenario:** User built from git commit after latest release

**Output Format:**
```
Running development version (0.3.0-dev)

Latest stable release: 0.2.0
View releases: https://github.com/941design/textbrush/releases
```

### FR6: Error Handling

**Requirement:** Graceful handling of network and API errors

**Network Failure:**
```
Failed to check for updates: Network error
Please check your internet connection and try again.

View releases manually: https://github.com/941design/textbrush/releases
```

**API Rate Limit (GitHub API: 60 req/hour unauthenticated):**
```
Failed to check for updates: GitHub API rate limit exceeded
Please wait a few minutes and try again.

View releases manually: https://github.com/941design/textbrush/releases
```

**Invalid Response:**
```
Failed to check for updates: Unexpected API response
Please try again later.

View releases manually: https://github.com/941design/textbrush/releases
```

**All Errors:** Exit with code 0 (update check is informational, not critical)

## Critical Constraints

### Privacy and Security

1. **No Automatic Checks:**
   - Update check ONLY when user explicitly runs `--check-updates`
   - No background checks, no scheduled checks
   - No telemetry or usage tracking

2. **No Auto-Update:**
   - Only manual downloads from GitHub Releases
   - Never modify installed files
   - Never download binaries automatically

3. **API Usage:**
   - Use unauthenticated GitHub API (60 req/hour limit)
   - No tokens or credentials required
   - Respect rate limits gracefully

4. **Data Collection:**
   - No user data sent to GitHub (API is read-only)
   - No analytics or metrics
   - No version checking on app startup

### Technical Constraints

1. **Dependencies:**
   - Use `packaging` library for version comparison (already in dev deps)
   - Use `urllib` or `requests` for HTTP requests
   - No additional heavyweight dependencies

2. **Network:**
   - Timeout: 5 seconds for GitHub API request
   - No retries (single attempt only)
   - User-Agent header: `textbrush/<version>` for identification

3. **Caching:**
   - No caching of update check results
   - Each `--check-updates` makes fresh API call
   - User controls frequency of checks

### User Experience Constraints

1. **Performance:**
   - Update check should complete in <2 seconds on good network
   - Timeout at 5 seconds if network slow
   - Non-blocking (doesn't slow down generation workflow)

2. **Simplicity:**
   - No configuration options (hardcoded GitHub repo)
   - No interactive prompts
   - Clear output with actionable next steps

3. **Consistency:**
   - Follow existing error message style
   - Use same URL formatting as other commands
   - Respect `--verbose` flag for debug output

## Integration Points

### CLI Module (`textbrush/cli.py`)

**Changes Required:**
```python
parser.add_argument(
    "--check-updates",
    action="store_true",
    help="Check for newer textbrush releases"
)

# In main():
if args.check_updates:
    # Validate conflicts
    if args.prompt or args.download_model or args.headless:
        print("Error: --check-updates cannot be used with other flags", file=sys.stderr)
        sys.exit(1)

    from textbrush.updates import check_for_updates
    check_for_updates(verbose=args.verbose)
    sys.exit(0)
```

### New Module: `textbrush/updates.py`

**Functions:**
- `get_current_version() -> str` - Read from pyproject.toml
- `get_latest_release() -> dict` - Query GitHub API
- `compare_versions(current: str, latest: str) -> str` - "update" | "current" | "dev"
- `check_for_updates(verbose: bool = False) -> None` - Main entry point

**Implementation Notes:**
- Parse `pyproject.toml` with `tomllib` (Python 3.11+)
- Use `urllib.request` for GitHub API (no external deps)
- Handle JSON parsing with `json` module
- Version comparison with `packaging.version.Version`

### Version File (`pyproject.toml`)

**No Changes Required:**
- Version already defined: `version = "0.1.0"`
- Update process already uses semantic versioning
- Existing version bump workflow continues unchanged

## Out of Scope

- Automatic update checks on app startup
- Background update checks
- Notifications in the UI (only CLI flag)
- Auto-update or automatic downloads
- Version pinning or update blocking
- Release notes fetching (only link provided)
- Beta/prerelease channel support
- Custom GitHub repo configuration
- Authenticated GitHub API (use public API only)
- Offline mode or cached update info
- Comparison with specific version (always latest)
- `--update` command to actually perform update

## Success Criteria

### Functional Acceptance

1. **Update Available:**
   ```bash
   # Assuming current=0.1.0, latest=0.2.0
   textbrush --check-updates
   # Prints update notification with download links
   # Exits with code 0
   ```

2. **Up to Date:**
   ```bash
   # Assuming current=latest
   textbrush --check-updates
   # Prints "up to date" message
   # Exits with code 0
   ```

3. **Development Version:**
   ```bash
   # Assuming current=0.3.0, latest=0.2.0
   textbrush --check-updates
   # Prints development version message
   # Exits with code 0
   ```

4. **Network Error:**
   ```bash
   # With network disconnected
   textbrush --check-updates
   # Prints error with manual link
   # Exits with code 0
   ```

5. **Conflict Detection:**
   ```bash
   textbrush --check-updates --prompt "test"
   # Prints error about conflicting flags
   # Exits with code 1
   ```

6. **Help Text:**
   ```bash
   textbrush --help
   # Shows --check-updates flag with description
   ```

### Non-Functional Acceptance

1. **Performance:** Check completes in <2 seconds on good network
2. **Privacy:** No data sent to GitHub beyond API request (read-only)
3. **Reliability:** Graceful handling of all network/API errors
4. **User Experience:** Clear, actionable messages with download links

## Implementation Notes

**Estimated Effort:** Medium (3-4 hours)

**Dependencies:**
- `packaging` - Already in dev dependencies
- `tomllib` - Standard library (Python 3.11+)
- `urllib` - Standard library
- `json` - Standard library

**Testing Requirements:**
- Unit tests for version comparison logic
- Unit tests for current version detection
- Mock GitHub API responses for integration tests
- Error case tests (network failure, rate limit, invalid JSON)
- E2E test with actual GitHub API (CI only, not in regular tests)

**Rollout Plan:**
1. Implement `textbrush/updates.py` module
2. Add CLI flag and logic to `textbrush/cli.py`
3. Add comprehensive tests (unit + integration)
4. Update documentation (README, user-stories)
5. Mark user story as [Implemented] in user-stories.md

**GitHub API Details:**

**Endpoint:** `GET https://api.github.com/repos/941design/textbrush/releases/latest`

**Response Format:**
```json
{
  "tag_name": "v0.2.0",
  "name": "Release 0.2.0",
  "html_url": "https://github.com/941design/textbrush/releases/tag/v0.2.0",
  "assets": [
    {
      "name": "textbrush-aarch64-apple-darwin.tar.gz",
      "browser_download_url": "https://github.com/.../textbrush-aarch64-apple-darwin.tar.gz"
    }
  ]
}
```

**Rate Limits:**
- Unauthenticated: 60 requests/hour per IP
- Adequate for manual checks
- No need for authentication

**Future Enhancements (Not in Scope):**
- Authenticated API for higher rate limits
- Cache last check result for 1 hour
- `--update` command to auto-download and install
- Check for updates on app startup (with opt-out)
- Prerelease channel support
- Notification in UI (not just CLI)
