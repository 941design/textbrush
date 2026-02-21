---
epic: produce-dmg-release-artifacts-for-macos
created: 2026-02-21T21:16:59Z
status: initializing
---

# Feature Specification: Produce .dmg Release Artifacts for macOS

**Status:** Planned (Not Implemented)
**Priority:** Low
**Target Version:** TBD

## Problem Statement

The spec (spec.md:378) states:

> Binary packaging: .app, .dmg (macOS), .tar.gz (Linux)

The Tauri config (tauri.conf.json:12) includes dmg as a bundle target:

```json
"targets": ["app", "dmg"]
```

However, the release workflow (`.github/workflows/release.yml:44-56`) builds via `cargo build` directly and manually packages the `.app` into a tarball:

```yaml
- name: Build release
  run: |
    uv sync
    cd src-tauri
    cargo build --target ${{ matrix.target }} --release

- name: Package macOS
  if: startsWith(matrix.os, 'macos')
  run: |
    cd src-tauri/target/${{ matrix.target }}/release/bundle/macos
    tar -czf ${{ matrix.asset_name }}.tar.gz *.app
```

This bypasses Tauri's bundler entirely. The Tauri bundler (`cargo tauri build`) is what produces `.dmg` files, but it's never invoked in the release workflow.

The result: macOS release artifacts are `.tar.gz` of `.app` bundles, not `.dmg` disk images. Users must extract the tarball manually instead of mounting a familiar dmg.

## Core Functionality

Update the release workflow to use `cargo tauri build` instead of `cargo build`, producing proper `.dmg` artifacts for macOS alongside `.app` tarballs.

## Functional Requirements

### FR1: Use Tauri Build in Release Workflow

**Requirement:** Replace `cargo build` with `cargo tauri build` for the release build step.

**Current:**
```yaml
- name: Build release
  run: |
    uv sync
    cd src-tauri
    cargo build --target ${{ matrix.target }} --release
```

**Required:**
```yaml
- name: Install Tauri CLI
  run: cargo install tauri-cli

- name: Build release
  run: |
    uv sync
    cargo tauri build --target ${{ matrix.target }}
```

**Rationale:** `cargo tauri build` invokes the Tauri bundler which produces both `.app` and `.dmg` artifacts according to the `bundle.targets` config.

### FR2: Upload .dmg as Release Asset

**Requirement:** Add the `.dmg` file to the release assets for macOS builds.

**Expected output location:** `src-tauri/target/${{ matrix.target }}/release/bundle/dmg/*.dmg`

**Package step:**
```yaml
- name: Package macOS
  if: startsWith(matrix.os, 'macos')
  run: |
    # App tarball (for users who prefer it)
    cd src-tauri/target/${{ matrix.target }}/release/bundle/macos
    tar -czf ${{ matrix.asset_name }}.tar.gz *.app
    shasum -a 256 ${{ matrix.asset_name }}.tar.gz > ${{ matrix.asset_name }}.tar.gz.sha256
    mv ${{ matrix.asset_name }}.tar.gz* ../../../../../..

    # DMG (primary macOS distribution format)
    cd ../dmg
    DMG_FILE=$(ls *.dmg)
    shasum -a 256 "$DMG_FILE" > "$DMG_FILE.sha256"
    mv "$DMG_FILE" "$DMG_FILE.sha256" ../../../../../..
```

### FR3: Update Upload Step

**Requirement:** Include `.dmg` and its checksum in the upload files list.

```yaml
- name: Upload release assets
  uses: softprops/action-gh-release@v1
  with:
    files: |
      ${{ matrix.asset_name }}.tar.gz
      ${{ matrix.asset_name }}.tar.gz.sha256
      *.dmg
      *.dmg.sha256
```

### FR4: Update Release Body

**Requirement:** Update the release notes template to include `.dmg` download instructions.

**macOS section:**
```markdown
### macOS
1. Download `Textbrush_x.y.z_aarch64.dmg` (Apple Silicon) or `Textbrush_x.y.z_x64.dmg` (Intel)
2. Open the .dmg and drag Textbrush to Applications
3. Run `xattr -cr /Applications/Textbrush.app` to bypass Gatekeeper
4. Launch the app or use CLI: `/Applications/Textbrush.app/Contents/MacOS/textbrush --prompt "Your prompt"`

Alternative: Download the .tar.gz and extract manually.
```

## Critical Constraints

1. **Signing.** The spec (spec.md:632) says "Non-Apple signing (ad-hoc codesign), Not notarized." Tauri's bundler handles ad-hoc signing by default. The current config has `"signingIdentity": "-"` which is ad-hoc. No notarization step needed.
2. **Tauri CLI version.** The `cargo tauri build` command must use a Tauri CLI version compatible with the project's Tauri dependency.
3. **Build time.** `cargo tauri build` may take longer than `cargo build` due to bundling steps. Acceptable for release builds.
4. **Linux unaffected.** Linux builds don't produce dmg. The Linux packaging step remains unchanged.
5. **Both formats.** Continue uploading `.tar.gz` of `.app` alongside `.dmg` for users who prefer it.

## Integration Points

### Release Workflow (`.github/workflows/release.yml`)
- Build step: Replace `cargo build` with `cargo tauri build`
- Package step: Add dmg handling for macOS
- Upload step: Add dmg files to asset list
- Release body: Update installation instructions

### Tauri Config (`src-tauri/tauri.conf.json`)
- Already has `"targets": ["app", "dmg"]` — no change needed

### Spec (`specs/spec.md`)
- Already says `.dmg` — no change needed after fix

## Out of Scope

- Apple Developer signing (paid certificate)
- Notarization via Apple's notary service
- Windows MSI/NSIS installers
- Linux .deb or .AppImage packaging
- Auto-update mechanisms via Tauri's updater

## Success Criteria

1. macOS release artifacts include both `.dmg` and `.tar.gz` files with SHA256 checksums.
2. The `.dmg` mounts correctly and contains the `.app` bundle.
3. The `.app` inside the `.dmg` launches correctly after Gatekeeper bypass.
4. Linux builds continue to produce `.tar.gz` as before.
5. Release notes include `.dmg` installation instructions.
