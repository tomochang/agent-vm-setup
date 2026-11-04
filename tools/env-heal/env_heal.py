#!/usr/bin/env python3
"""env_heal — repair one specific, recurring failure in this VM.

Failure pattern (seen 3x on 2026-11-02): a VM replacement wipes /usr, and an
`apt-get update` from the boot-time replay stalls through the proxy while
holding the apt lock, so bootstrap.sh can never reinstall ruby and
records_gate stays blocked.

What this does, and only this:
  1. Run bootstrap-check. If ruby/yaml is not the FAIL, do nothing.
  2. If ruby/yaml FAILs: find processes that are exactly `apt-get update`.
     - A young one (< ENV_HEAL_STALL_SECONDS old) is given up to
       ENV_HEAL_YOUNG_WAIT seconds to finish on its own.
     - One still alive past the stall threshold is terminated
       (TERM, then KILL after 3s). `apt-get install`, dpkg and anything
       else are NEVER touched.
  3. `apt-get update` (timeout), then `apt-get install -y ruby` (timeout).
  4. Re-run bootstrap-check. Verdict: healed / failed / no-op.

Fail-open: any unexpected error is reported as "failed" with the reason and
exit code 1, so the caller (heartbeat / a human) surfaces it as before.
Every run prints one JSON line and appends it to env-heal.log.
"""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
CHECK = Path(os.environ.get("BOOTSTRAP_CHECK", str(HOME / "workspace/tools/bootstrap-check.sh")))
LOG = HOME / "workspace/tools/env-heal.log"
STALL_SECONDS = int(os.environ.get("ENV_HEAL_STALL_SECONDS", "600"))
YOUNG_WAIT = int(os.environ.get("ENV_HEAL_YOUNG_WAIT", "90"))


def run(cmd, timeout=None):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def check_output():
    try:
        return run(["bash", str(CHECK)], timeout=60).stdout
    except Exception:
        return ""


def ruby_failing():
    return "FAIL ruby/yaml" in check_output()


def apt_update_pids():
    """PIDs running `apt-get update` and nothing else. Returns
    {pid: age_seconds}. The subcommand is the first token that is a known
    apt subcommand — option values (e.g. the argument of -o) must not be
    mistaken for it (bug found in testing, 2026-11-02)."""
    subcommands = {"update", "install", "upgrade", "dist-upgrade", "remove",
                   "purge", "autoremove", "check", "download", "source"}
    found = {}
    for proc in Path("/proc").glob("[0-9]*"):
        try:
            tokens = (proc / "cmdline").read_bytes().split(b"\0")
            tokens = [t.decode(errors="replace") for t in tokens if t]
        except OSError:
            continue
        if not tokens or Path(tokens[0]).name != "apt-get":
            continue
        subs = [t for t in tokens[1:] if t in subcommands]
        if not subs or subs[0] != "update":
            continue
        pid = int(proc.name)
        try:
            age = int(run(["ps", "-o", "etimes=", "-p", str(pid)]).stdout.strip())
        except Exception:
            continue
        found[pid] = age
    return found


def main():
    result = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "verdict": None, "actions": []}

    if not ruby_failing():
        result["verdict"] = "no-op"
        other = [ln for ln in check_output().splitlines() if ln.startswith("FAIL")]
        if other:
            result["other_fails_untouched"] = other
        emit(result)
        return 0

    # Step 1: deal with apt-get update processes holding the lock.
    deadline = time.time() + YOUNG_WAIT
    while True:
        procs = apt_update_pids()
        if not procs:
            break
        young = {p: a for p, a in procs.items() if a < STALL_SECONDS}
        if young and time.time() < deadline:
            time.sleep(5)
            continue
        for pid, age in procs.items():
            if age >= STALL_SECONDS:
                try:
                    os.kill(pid, signal.SIGTERM)
                    result["actions"].append(f"killed stalled apt-get update pid={pid} age={age}s")
                except OSError as e:
                    result["actions"].append(f"kill failed pid={pid}: {e}")
        time.sleep(3)
        for pid in list(apt_update_pids()):
            try:
                os.kill(pid, signal.SIGKILL)
                result["actions"].append(f"sigkill pid={pid}")
            except OSError:
                pass
        break

    # Step 2: the proven manual fix — update, then install ruby.
    try:
        r = run(["apt-get", "update"], timeout=150)
        result["actions"].append(f"apt-get update rc={r.returncode}")
    except subprocess.TimeoutExpired:
        result["actions"].append("apt-get update TIMED OUT")
    try:
        r = run(["apt-get", "install", "-y", "ruby"], timeout=240)
        result["actions"].append(f"apt-get install ruby rc={r.returncode}")
    except subprocess.TimeoutExpired:
        result["actions"].append("apt-get install ruby TIMED OUT")

    result["verdict"] = "failed" if ruby_failing() else "healed"
    emit(result)
    return 0 if result["verdict"] == "healed" else 1


def emit(result):
    line = json.dumps(result, ensure_ascii=False)
    print(line)
    try:
        with open(LOG, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # fail-open: report, never wedge the caller
        emit({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
              "verdict": "failed", "actions": [f"exception: {e}"]})
        sys.exit(1)
