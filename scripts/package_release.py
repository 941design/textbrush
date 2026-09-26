"""Validate platform build outputs before preparing checksum-labelled uploads."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import tarfile
from pathlib import Path


def collect(build: Path, output: Path, asset_name: str, platform: str) -> list[Path]:
    if Path(asset_name).name != asset_name or not asset_name:
        raise ValueError("asset_name must be a filename, not a path")
    if platform not in {"macos", "linux"}:
        raise ValueError(f"Unsupported platform: {platform}")
    if platform == "macos":
        archive_source = build / "bundle/macos/Textbrush.app"
        required_binary = archive_source / "Contents/MacOS/textbrush"
        installers = list((build / "bundle/dmg").glob("*.dmg"))
    else:
        archive_source = required_binary = build / "textbrush"
        installers = list((build / "bundle/deb").glob("*.deb"))
    if not required_binary.is_file() or required_binary.stat().st_size == 0:
        raise ValueError(f"Missing or empty native executable: {required_binary}")
    if len(installers) != 1 or installers[0].stat().st_size == 0:
        raise ValueError(f"Expected exactly one nonempty {platform} installer, found {installers}")
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Upload directory must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"{asset_name}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(archive_source, arcname=archive_source.name)
    installer = output / installers[0].name
    shutil.copyfile(installers[0], installer)
    files = [archive, installer]
    for file in files.copy():
        with file.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        checksum = file.with_name(file.name + ".sha256")
        checksum.write_text(f"{digest}  {file.name}\n")
        files.append(checksum)
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--asset-name", required=True)
    args = parser.parse_args()
    if args.target.endswith("apple-darwin"):
        platform = "macos"
    elif args.target.endswith("unknown-linux-gnu"):
        platform = "linux"
    else:
        parser.error(f"Unsupported release target: {args.target}")
    root = Path(__file__).resolve().parent.parent
    files = collect(
        root / "src-tauri/target" / args.target / "release",
        root / "release-assets",
        args.asset_name,
        platform,
    )
    for file in files:
        print(file.relative_to(root))


if __name__ == "__main__":
    main()
