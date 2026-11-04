#!/usr/bin/env python3
"""mechanism_coverage_check — every mechanism the resident agent operates must be
recorded in records (the SoT), not only in this VM.

Born from the 2026-11-03 factory-handoff miss: a new repo + protocol was
built and already operating (ack exchanged, cycle test run, a real task
placed) while its only records were the side repo itself and VM working
files. the operator caught it ("この仕組み、mainにpushされてない"). The
reproducibility rule already required a landed doc; what was missing was
a machine check, because doc_coverage_check only covers scripts in the
tool directories — a new repository is not a script.

Coverage (default-deny):
  - every git repository directly under ~/workspace, except `records`
    itself (the SoT) and worktree checkouts (~/records-wt/*)
  - every topic dir under ~/workspace/research that holds a spec.md,
    SPEC.md or trial.md (research that turned into a mechanism)
  - every topic dir under ~/workspace/research that holds a finished
    deliverable (digest.json, digest.html or report.html) — added
    2026-11-03 after the agent-vs-vanilla imozuru research was presented
    to the operator before it was landed to records (failure-ledger signature
    `research-deliverable-not-landed`, the second strike in the
    mechanism-without-records-record family)
A mechanism target is covered when its name appears in at least one
document under origin/main:docs/infra/. A deliverable topic is covered
when research/<topic>/ itself exists in origin/main (the deliverable IS
the record) or, failing that, when its name appears in a landed doc the
same way. EXCLUSIONS below are explicit exceptions, each with a reason;
an exclusion must also be named in the procedure doc.

Prints OK/FAIL per target and exits 1 on any FAIL. Existence only, not
quality — same division as doc_coverage_check. If `git fetch` fails, the
last fetched origin/main is used and marked stale.
"""
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
WORKSPACE = Path(os.environ.get("AGENT_VM_ROOT", str(HOME / "workspace")))
RECORDS = Path(os.environ.get("RECORDS_DIR", str(WORKSPACE / "records")))

EXCLUSIONS = {
    # name: reason (each must also appear in the procedure doc)
}

SPEC_NAMES = {"spec.md", "SPEC.md", "trial.md"}
DELIVERABLE_NAMES = {"digest.json", "digest.html", "report.html"}


def targets():
    """Return (mechanisms, deliverables): name -> description dicts."""
    mechanisms = {}
    deliverables = {}
    for child in sorted(WORKSPACE.iterdir()):
        if child.name in ("records", "records-wt"):
            continue
        if (child / ".git").exists():
            mechanisms[child.name] = f"repo {child}"
    research = WORKSPACE / "research"
    if research.is_dir():
        for child in sorted(research.iterdir()):
            if not child.is_dir():
                continue
            if any((child / s).exists() for s in SPEC_NAMES):
                mechanisms[child.name] = f"research mechanism {child}"
            if any((child / d).exists() for d in DELIVERABLE_NAMES):
                deliverables[child.name] = f"research deliverable {child}"
    return mechanisms, deliverables


def covered(name):
    r = subprocess.run(
        ["git", "-C", str(RECORDS), "grep", "-F", "-l", name, "origin/main", "--", "docs/infra/"],
        capture_output=True, text=True,
    )
    return r.returncode == 0 and bool(r.stdout.strip())


def landed_research(name):
    r = subprocess.run(
        ["git", "-C", str(RECORDS), "ls-tree", "origin/main", "--", f"research/{name}"],
        capture_output=True, text=True,
    )
    return r.returncode == 0 and bool(r.stdout.strip())


def main():
    stale = False
    r = subprocess.run(["git", "-C", str(RECORDS), "fetch", "-q", "origin"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        stale = True
    mechanisms, deliverables = targets()
    fails = []
    for name in sorted(set(mechanisms) | set(deliverables)):
        if name in mechanisms and name in deliverables:
            desc = f"{mechanisms[name]} + deliverable"
        elif name in mechanisms:
            desc = mechanisms[name]
        else:
            desc = deliverables[name]
        if name in EXCLUSIONS:
            print(f"EXCLUDED {name} ({desc}) — {EXCLUSIONS[name]}")
            continue
        named = covered(name)
        missing = []
        if name in mechanisms and not named:
            missing.append("no landed doc under docs/infra names it")
        if name in deliverables and not (named or landed_research(name)):
            missing.append("deliverable not landed at origin/main:research/<topic> "
                           "and not named in a landed doc under docs/infra")
        if missing:
            print(f"FAIL {name} ({desc}) — " + "; ".join(missing))
            fails.append(name)
        else:
            print(f"OK {name} ({desc})")
    if stale:
        print("NOTE stale: git fetch failed; judged against last fetched origin/main")
    print(f"mechanism_coverage: {'FAIL ' + ','.join(fails) if fails else 'OK'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
