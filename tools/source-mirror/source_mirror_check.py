#!/usr/bin/env python3
"""Byte-for-byte drift check between the agent-VM tool sources and their records mirror.

clawd is the source of truth: the canonical copies of these tool sources live
in clawd at tools/mofu-vm/. The VM files are runtime working copies. This
checker fails (exit 1) when any runtime source is missing from the mirror,
differs from it, or when the mirror holds a .py/.sh file with no runtime
source. It reads only source files (*.py / *.sh) from the runtime roots and
the mirror; it never reads credential files, runtime data, or state.

Usage:
    python3 source_mirror_check.py [--mirror-root PATH]

Defaults: workspace root = parent of this script's tools/ directory;
mirror root = <workspace>/clawd/tools/mofu-vm.
"""
import argparse
import sys
from pathlib import Path

# One-off diagnostics from the 2026-11-01 Beeper OAuth sign-in session.
# Excluded from the mirror; doc_coverage_check.py marks the same set EXCLUDED.
EXCLUDED_BEEPER = {
    "drive_login.py",
    "enter_code.py",
    "oauth_approve.py",
    "oauth_continue.py",
    "oauth_drive.py",
    "oauth_prompt_inspect.py",
    "oauth_prompt_inspect2.py",
    "oauth_prompt_never.py",
    "oauth_prompt_rows.py",
    "page_text.py",
}

SOURCE_SUFFIXES = (".py", ".sh")


def build_manifest(workspace: Path, home: Path):
    """Return {mirror_relative_path: runtime_source_path}."""
    manifest = {}

    def add(src_dir: Path, mirror_prefix: str, excluded=frozenset()):
        if not src_dir.is_dir():
            return
        for p in sorted(src_dir.iterdir()):
            if p.is_file() and p.suffix in SOURCE_SUFFIXES and p.name not in excluded:
                manifest[f"{mirror_prefix}/{p.name}"] = p

    add(workspace / "tools", "tools")
    add(workspace / "beeper-diag", "beeper-diag", EXCLUDED_BEEPER)
    add(home / "hooks" / "scripts", "hooks/scripts")
    # vm-bootstrap: only bootstrap.sh is a runtime source there.
    bs = workspace / "vm-bootstrap" / "bootstrap.sh"
    if bs.is_file():
        manifest["vm-bootstrap/bootstrap.sh"] = bs
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mirror-root", type=Path, default=None,
                    help="Mirror root (default: <workspace>/clawd/tools/mofu-vm)")
    ap.add_argument("--workspace", type=Path, default=None,
                    help="Workspace root (default: parent of this script's tools dir)")
    args = ap.parse_args()

    tools_dir = Path(__file__).resolve().parent
    workspace = (args.workspace or tools_dir.parent).resolve()
    home = Path.home()
    mirror_root = (args.mirror_root or (workspace / "clawd" / "tools" / "mofu-vm")).resolve()

    manifest = build_manifest(workspace, home)
    failures = 0

    for rel, src in sorted(manifest.items()):
        dst = mirror_root / rel
        if not dst.is_file():
            print(f"FAIL missing in mirror: {rel}")
            failures += 1
        elif dst.read_bytes() != src.read_bytes():
            print(f"FAIL differs: {rel}")
            failures += 1
        else:
            print(f"OK {rel}")

    if mirror_root.is_dir():
        expected = set(manifest)
        for p in sorted(mirror_root.rglob("*")):
            if p.is_file() and p.suffix in SOURCE_SUFFIXES:
                rel = p.relative_to(mirror_root).as_posix()
                if rel not in expected:
                    print(f"FAIL extra in mirror: {rel}")
                    failures += 1
    else:
        print(f"FAIL mirror root not found: {mirror_root}")
        failures += 1

    if failures:
        print(f"source_mirror_check: FAIL ({failures} problem(s), {len(manifest)} sources checked)")
        return 1
    print(f"source_mirror_check: OK ({len(manifest)} sources byte-identical)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
