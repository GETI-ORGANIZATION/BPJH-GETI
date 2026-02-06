#!/usr/bin/env python3
"""Install a skill from GitHub into a local skills directory.

Thin CLI wrapper around EvoScientist.skills_manager — all clone, resolve,
and validation logic lives in the core module.

Usage examples:
    # Install from a GitHub URL (auto-detects repo, ref, path)
    python install_skill.py --url https://github.com/anthropics/skills/tree/main/excel

    # Install from shorthand
    python install_skill.py --url anthropics/skills@excel

    # Install from repo + path(s)
    python install_skill.py --repo anthropics/skills --path excel
    python install_skill.py --repo anthropics/skills --path excel --path pdf

    # Install with a specific git ref
    python install_skill.py --repo org/repo --path my-skill --ref v2.0
"""

from __future__ import annotations

import argparse
import sys

from EvoScientist.skills_manager import install_skill, _parse_github_url


def _build_source(repo: str, ref: str | None, path: str | None) -> str:
    """Build a GitHub URL string that install_skill() can consume."""
    if ref and path:
        return f"https://github.com/{repo}/tree/{ref}/{path}"
    if ref:
        return f"https://github.com/{repo}/tree/{ref}"
    if path:
        return f"{repo}@{path}"
    return f"https://github.com/{repo}"


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

    # Parse source
    if args.url:
        repo, ref, path = _parse_github_url(args.url)
        ref = args.ref or ref
        paths = [path] if path else args.path
    else:
        repo = args.repo
        ref = args.ref
        paths = args.path

    # Install each path (or the whole repo if no paths given)
    sources = [_build_source(repo, ref, p) for p in paths] if paths else [_build_source(repo, ref, None)]

    installed = []
    for source in sources:
        print(f"Installing from: {source}")
        result = install_skill(source, dest_dir=args.dest)
        if result["success"]:
            print(f"  Installed: {result['name']} ({result.get('description', '')})")
            installed.append(result["name"])
        else:
            print(f"  Failed: {result['error']}", file=sys.stderr)

    if installed:
        print(f"\nInstalled {len(installed)} skill(s) to {args.dest}/:")
        for name in installed:
            print(f"  - {name}")
        return 0
    else:
        print("No skills were installed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
