#!/usr/bin/env python3
"""doc_coverage_check — every operational tool must have a landed doc.

Born from the 2026-11-02 env_heal miss: a tool was built, wired into
HEARTBEAT, and called done while its procedure doc had never been landed
in clawd docs/infra (the operator's reproducibility rule). Extended the same
night at the operator's probing ("what about the ones NOT in HEARTBEAT?") from
HEARTBEAT-wired tools to the full tool directories.

Coverage (default-deny: a new script in these dirs FAILs until documented):
  - every *.py / *.sh in ~/workspace/tools/, ~/workspace/beeper-diag/,
    and ~/hooks/scripts/
  - plus every tool path referenced from ~/HEARTBEAT.md
  - minus EXCLUSIONS below (one-off diagnostics; each exclusion is named
    here AND in the health-tools doc, so the exception is itself recorded)

For each covered tool, its name stem must appear in at least one landed
document under origin/main:docs/infra/. Prints OK/FAIL per tool, an
EXCLUDED section, and exits 1 on any FAIL. Existence only, not quality.
DOC_COVERAGE_HEARTBEAT overrides the heartbeat path (tests). If
`git fetch` fails, the last fetched origin/main is used and marked stale.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
HEARTBEAT = Path(os.environ.get("DOC_COVERAGE_HEARTBEAT", HOME / "HEARTBEAT.md"))
CLAWD = Path(os.environ.get("RECORDS_DIR", str(HOME / "workspace/clawd")))
_tool_dirs = os.environ.get("AGENT_TOOL_DIRS")
TOOL_DIRS = ([Path(d) for d in _tool_dirs.split(":")] if _tool_dirs else
             [HOME / "workspace/tools", HOME / "workspace/beeper-diag",
              HOME / "hooks/scripts"])
TOOL_RE = re.compile(r"((?:tools|beeper-diag)/[\w.\-]+\.(?:py|sh))")

# One-off UI-driving diagnostics from the 2026-11-01 Beeper OAuth sign-in
# session. Not wired into anything; the durable path is oauth_setup.py +
# beeper_api.py. Listed here so the exclusion is explicit, not silent.
EXCLUSIONS = {
    "drive_login.py", "enter_code.py", "oauth_approve.py",
    "oauth_continue.py", "oauth_drive.py", "oauth_prompt_inspect.py",
    "oauth_prompt_inspect2.py", "oauth_prompt_never.py",
    "oauth_prompt_rows.py", "page_text.py",
}
EXCLUSION_REASON = ("one-off diagnostics from the 2026-11-01 Beeper OAuth "
                    "sign-in session; superseded by oauth_setup.py / beeper_api.py")


def run(cmd, timeout=None):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def main():
    stale = False
    try:
        r = run(["git", "-C", str(CLAWD), "fetch", "--quiet", "origin"], timeout=30)
        stale = r.returncode != 0
    except Exception:
        stale = True

    covered = {}   # display path -> file name
    excluded = []
    for d in TOOL_DIRS:
        for f in sorted(d.iterdir()):
            if f.suffix not in (".py", ".sh") or not f.is_file():
                continue
            rel = str(f.relative_to(HOME))
            if f.name in EXCLUSIONS:
                excluded.append(rel)
            else:
                covered[rel] = f.name
    if HEARTBEAT.exists():
        have = {name for name in covered.values()}
        for rel in sorted(set(TOOL_RE.findall(HEARTBEAT.read_text()))):
            if Path(rel).name not in have:
                covered.setdefault(rel, Path(rel).name)

    if not covered:
        print("FAIL no tools found (enumeration problem?)")
        return 1

    fail = 0
    for rel, name in sorted(covered.items()):
        stem = Path(name).stem
        r = run(["git", "-C", str(CLAWD), "grep", "-l", stem, "origin/main", "--", "docs/infra/"])
        docs = [ln.split(":", 1)[1] for ln in r.stdout.splitlines() if ":" in ln]
        if docs:
            print(f"OK   {rel} — documented in {docs[0]}")
        else:
            print(f"FAIL {rel} — no landed procedure doc under docs/infra/ mentions {stem}")
            fail = 1
    for rel in excluded:
        print(f"EXCLUDED {rel} — {EXCLUSION_REASON}")
    if stale:
        print("WARN origin/main may be stale (fetch failed); results use the last fetched ref")
    return fail


if __name__ == "__main__":
    sys.exit(main())
