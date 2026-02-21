# Acceptance Criteria: Produce .dmg Release Artifacts for macOS

Generated: 2026-02-21T21:17:45Z
Source: spec.md

## Criteria

### AC-001: Release workflow uses cargo tauri build instead of cargo build
- **Description**: The Build release step in .github/workflows/release.yml must invoke `cargo tauri build` (not `cargo build`) and must be preceded by a step that installs tauri-cli
- **Verification**: Read .github/workflows/release.yml and confirm: (1) a step installing tauri-cli exists before the build step, (2) the build step uses `cargo tauri build --target ${{ matrix.target }}` without `--release` flag (tauri build implies release), (3) no `cd src-tauri` before the tauri build (tauri-cli runs from project root)
- **Type**: manual

### AC-002: macOS release artifacts include .dmg with checksum
- **Description**: The Package macOS step must generate a .dmg artifact with SHA256 checksum alongside the existing .tar.gz artifacts
- **Verification**: Read release.yml and confirm the Package macOS step: (1) navigates to bundle/dmg directory, (2) runs shasum -a 256 on the .dmg file, (3) moves both the .dmg and .dmg.sha256 to the workspace root
- **Type**: manual

### AC-003: Upload step includes .dmg and checksum
- **Description**: The Upload release assets step must include *.dmg and *.dmg.sha256 in the files list
- **Verification**: Read release.yml and confirm the files section under Upload release assets contains *.dmg and *.dmg.sha256 entries
- **Type**: manual

### AC-004: Release body includes .dmg installation instructions
- **Description**: The release notes body must reference .dmg files as the primary macOS distribution format with correct filenames (Textbrush_x.y.z_aarch64.dmg pattern) and include drag-to-Applications instructions
- **Verification**: Read release.yml and confirm the body section includes .dmg download instructions with drag-to-Applications step and Gatekeeper bypass command
- **Type**: manual

### AC-005: Linux packaging remains unchanged
- **Description**: The Linux Package step and Linux-specific behavior must be unaffected by changes
- **Verification**: Read release.yml and confirm Package Linux step is unchanged: still uses tar.gz of the textbrush binary, uses sha256sum, and moves to workspace root
- **Type**: manual

### AC-006: Tauri config unchanged
- **Description**: src-tauri/tauri.conf.json already has the correct bundle targets and should not be modified
- **Verification**: Read tauri.conf.json and confirm bundle.targets = ["app", "dmg"] and signingIdentity = "-" remain unchanged
- **Type**: manual

## Verification Plan

All verification is static analysis of the YAML workflow file since GitHub Actions cannot be executed locally. Each criterion is verified by reading .github/workflows/release.yml and checking specific structural properties:

1. Run `cat .github/workflows/release.yml` and inspect each modified section
2. Verify the Install Tauri CLI step exists before Build release
3. Verify Build release uses `cargo tauri build` at project root
4. Verify Package macOS step handles both .app and .dmg with checksums
5. Verify Upload step includes both tar.gz and dmg files
6. Verify release body has updated macOS instructions
7. Verify Linux Package step is unchanged
8. Verify tauri.conf.json is unmodified

Note: This feature has no E2E test scenarios as it modifies a GitHub Actions workflow file that cannot be executed in a local test environment. Functional verification requires an actual tag push and observing the Actions run. The acceptance criteria above represent the maximum testable verification in the local context.
