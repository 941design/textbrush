"""Release uploads must contain actual platform outputs and valid checksums."""

import hashlib
import tarfile

import pytest

from scripts.package_release import collect


@pytest.mark.parametrize("platform", ["macos", "linux"])
def test_collect_checksums_and_archive_layout(tmp_path, platform):
    build = tmp_path / "build with spaces"
    if platform == "macos":
        binary = build / "bundle/macos/Textbrush.app/Contents/MacOS/textbrush"
        installer = build / "bundle/dmg/Textbrush_arm64.dmg"
        member = "Textbrush.app/Contents/MacOS/textbrush"
    else:
        binary = build / "textbrush"
        installer = build / "bundle/deb/textbrush_arm64.deb"
        member = "textbrush"
    binary.parent.mkdir(parents=True)
    installer.parent.mkdir(parents=True)
    binary.write_bytes(b"native executable")
    installer.write_bytes(b"platform installer")
    output = tmp_path / "uploads"
    files = collect(build, output, f"textbrush-{platform}", platform)
    assert len(files) == 4
    for file in files:
        if file.suffix == ".sha256":
            digest, name = file.read_text().split()
            assert digest == hashlib.sha256((output / name).read_bytes()).hexdigest()
    with tarfile.open(output / f"textbrush-{platform}.tar.gz") as archive:
        assert archive.extractfile(member).read() == b"native executable"
    assert (output / installer.name).read_bytes() == b"platform installer"


@pytest.mark.parametrize(
    "missing", ["binary", "installer", "empty_installer", "duplicate_installer"]
)
def test_missing_or_ambiguous_build_fails_before_uploads(tmp_path, missing):
    build = tmp_path / "build"
    installers = build / "bundle/deb"
    installers.mkdir(parents=True)
    if missing != "binary":
        (build / "textbrush").write_bytes(b"binary")
    if missing != "installer":
        (installers / "app.deb").write_bytes(b"" if missing == "empty_installer" else b"deb")
    if missing == "duplicate_installer":
        (installers / "other.deb").write_bytes(b"deb")
    output = tmp_path / "uploads"
    with pytest.raises(ValueError):
        collect(build, output, "textbrush-linux", "linux")
    assert not output.exists()
