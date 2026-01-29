#!/usr/bin/env python3
"""Install a skill from GitHub into a local skills directory.

Self-contained installer — no external dependencies beyond git.

Usage examples:
    # Install from a GitHub URL (auto-detects repo, ref, path)
    python install_skill.py --url https://github.com/anthropics/skills/tree/main/excel

    # Install from repo + path
    python install_skill.py --repo anthropics/skills --path excel

    # Install multiple skills from the same repo
    python install_skill.py --repo anthropics/skills --path excel --path pdf

    # Install with a specific git ref
    python install_skill.py --repo org/repo --path my-skill --ref v2.0
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile


def parse_github_url(url: str) -> tuple[str, str | None, str | None]:
    """Parse a GitHub URL into (repo, ref, path).

    Supports formats:
        https://github.com/owner/repo
        https://github.com/owner/repo/tree/main/path/to/skill
        github.com/owner/repo/tree/branch/path
        owner/repo@skill-name  (shorthand from skills.sh)

    Returns:
        (repo, ref_or_none, path_or_none)
    """
    # Shorthand: owner/repo@path
    if "@" in url and "://" not in url:
        repo, path = url.split("@", 1)
        return repo.strip(), None, path.strip()

    # Strip protocol and github.com prefix
    cleaned = re.sub(r"^https?://", "", url)
    cleaned = re.sub(r"^github\.com/", "", cleaned)
    cleaned = cleaned.rstrip("/")

    # Match: owner/repo/tree/ref/path...
    m = re.match(r"^([^/]+/[^/]+)/tree/([^/]+)(?:/(.+))?$", cleaned)
    if m:
        return m.group(1), m.group(2), m.group(3)

    # Match: owner/repo (no tree)
    m = re.match(r"^([^/]+/[^/]+)$", cleaned)
    if m:
        return m.group(1), None, None

    raise ValueError(f"Cannot parse GitHub URL: {url}")


def clone_repo(repo: str, ref: str | None, dest: str) -> None:
    """Shallow-clone a GitHub repo."""
    clone_url = f"https://github.com/{repo}.git"
    cmd = ["git", "clone", "--depth", "1"]
    if ref:
        cmd += ["--branch", ref]
    cmd += [clone_url, dest]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"git clone failed: {result.stderr.strip()}")


def copy_skill(src: str, dest_dir: str) -> str:
    """Copy a skill directory to the destination.

    Returns:
        The skill name (directory basename).
    """
    skill_name = os.path.basename(src.rstrip("/"))
    target = os.path.join(dest_dir, skill_name)

    if os.path.exists(target):
        shutil.rmtree(target)
        print(f"  Replaced existing: {skill_name}")

    shutil.copytree(src, target)
    return skill_name


def validate_skill(path: str) -> bool:
    """Check that a directory looks like a valid skill (has SKILL.md)."""
    return os.path.isfile(os.path.join(path, "SKILL.md"))


def install(
    repo: str,
    paths: list[str],
    ref: str | None,
    dest: str,
) -> list[str]:
    """Install skill(s) from a GitHub repo.

    Returns:
        List of installed skill names.
    """
    os.makedirs(dest, exist_ok=True)
    installed: list[str] = []

    with tempfile.TemporaryDirectory(prefix="skill-install-") as tmp:
        clone_dir = os.path.join(tmp, "repo")
        print(f"Cloning {repo}" + (f" @{ref}" if ref else "") + "...")
        clone_repo(repo, ref, clone_dir)

        if not paths:
            # No path specified — treat entire repo as a single skill
            if validate_skill(clone_dir):
                name = copy_skill(clone_dir, dest)
                installed.append(name)
            else:
                # List top-level directories that look like skills
                for entry in sorted(os.listdir(clone_dir)):
                    entry_path = os.path.join(clone_dir, entry)
                    if os.path.isdir(entry_path) and validate_skill(entry_path):
                        name = copy_skill(entry_path, dest)
                        installed.append(name)

                if not installed:
                    print("No valid skills found in repository root.", file=sys.stderr)
        else:
            for p in paths:
                skill_path = os.path.join(clone_dir, p.strip("/"))
                if not os.path.isdir(skill_path):
                    print(f"  Path not found: {p}", file=sys.stderr)
                    continue
                if not validate_skill(skill_path):
                    print(f"  No SKILL.md in: {p}", file=sys.stderr)
                    continue
                name = copy_skill(skill_path, dest)
                installed.append(name)

    return installed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install skills from GitHub into a local skills directory.",
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--url",
        help="GitHub URL (e.g. https://github.com/owner/repo/tree/main/skill-name)",
    )
    src.add_argument(
        "--repo",
        help="GitHub repo (e.g. owner/repo)",
    )
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="Path to skill inside repo (repeatable)",
    )
    parser.add_argument(
        "--ref",
        default=None,
        help="Git branch or tag (default: repo default branch)",
    )
    parser.add_argument(
        "--dest",
        default="./skills",
        help="Destination directory (default: ./skills)",
    )

    args = parser.parse_args()
    dest = args.dest

    # Parse source
    if args.url:
        repo, ref, path = parse_github_url(args.url)
        ref = args.ref or ref
        paths = [path] if path else args.path
    else:
        repo = args.repo
        ref = args.ref
        paths = args.path

    try:
        installed = install(repo, paths, ref, dest)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if installed:
        print(f"\nInstalled {len(installed)} skill(s) to {dest}/:")
        for name in installed:
            print(f"  - {name}")
    else:
        print("No skills were installed.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
