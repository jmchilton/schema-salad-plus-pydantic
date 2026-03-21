#!/usr/bin/env python
"""Bump to next dev version after a release."""
import argparse
import re
import subprocess
import sys
from pathlib import Path

from packaging.version import Version

PROJECT_DIRECTORY = Path(__file__).parent.parent


class VersionBumper:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.history_path = project_dir / "HISTORY.rst"

    def get_current_version(self, source_dir: str) -> str:
        init_path = self.project_dir / source_dir / "__init__.py"
        content = init_path.read_text(encoding="utf-8")
        match = re.search(r'__version__ = ["\']([^"\']+)["\']', content)
        if not match:
            raise ValueError(f"Cannot find version in {init_path}")
        return match.group(1)

    def increment_version(self, version_str: str, bump_type: str = "patch") -> str:
        clean_version = version_str.split(".dev")[0]
        Version(clean_version)  # validate
        parts = clean_version.split(".")
        while len(parts) < 3:
            parts.append("0")
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
        if bump_type == "major":
            major, minor, patch = major + 1, 0, 0
        elif bump_type == "minor":
            minor, patch = minor + 1, 0
        else:
            patch += 1
        return f"{major}.{minor}.{patch}"

    def update_history_file(self, new_version: str) -> None:
        history = self.history_path.read_text(encoding="utf-8")
        marker = ".. to_doc\n"
        section = f"\n---------------------\n{new_version}.dev0\n---------------------\n\n"
        self.history_path.write_text(history.replace(marker, marker + section), encoding="utf-8")

    def update_init_file(self, source_dir: str, new_version: str) -> None:
        init_path = self.project_dir / source_dir / "__init__.py"
        content = init_path.read_text(encoding="utf-8")
        updated = re.sub(r'(__version__ = ["\'])[^"\']+(["\'])', rf"\g<1>{new_version}.dev0\g<2>", content)
        init_path.write_text(updated, encoding="utf-8")

    def commit_changes(self, source_dir: str, new_version: str) -> None:
        cmd = ["git", "commit", "-m", f"Starting work on {new_version}"] + [
            "HISTORY.rst",
            f"{source_dir}/__init__.py",
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)

    def bump_version(self, source_dir: str, bump_type: str = "patch") -> str:
        current = self.get_current_version(source_dir)
        new_version = self.increment_version(current, bump_type)
        self.update_history_file(new_version)
        self.update_init_file(source_dir, new_version)
        self.commit_changes(source_dir, new_version)
        return new_version


def main() -> None:
    parser = argparse.ArgumentParser(description="Bump to next dev version")
    parser.add_argument("source_dir")
    bump = parser.add_mutually_exclusive_group()
    bump.add_argument("--major", action="store_const", const="major", dest="bump_type")
    bump.add_argument("--minor", action="store_const", const="minor", dest="bump_type")
    bump.add_argument("--patch", action="store_const", const="patch", dest="bump_type")
    parser.set_defaults(bump_type="patch")

    args = parser.parse_args()
    bumper = VersionBumper(PROJECT_DIRECTORY)
    new_version = bumper.bump_version(args.source_dir, args.bump_type)
    print(f"Bumped to {new_version}.dev0")


if __name__ == "__main__":
    main()
