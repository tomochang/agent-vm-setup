#!/usr/bin/env python3
"""judge.py — the independent witness for the dead man's switch.

Polls healthchecks.io with the READ-ONLY API key every run (~15 min
from cron) and prints one line per state transition of the watched
checks. Silent when nothing changed. State lives in
~/.local/state/hc-judge-state.json (on the VM, never in git).

The one rule that matters: an API/auth failure is reported as an
AUTH problem (exit 4), never as "the target is down". A 401 after a
key rotation is an errand for the judge's owner, not an outage.

Credentials: ~/.config/healthchecks/credentials (600), keys:
  api_key_readonly=<read-only key>   (api_key_ro= also accepted)
Usage: judge.py [slug ...]   (default: every check in the account)
"""
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

CREDS = Path.home() / ".config" / "healthchecks" / "credentials"
STATE = Path.home() / ".local" / "state" / "hc-judge-state.json"
API = "https://healthchecks.io/api/v3/checks/"


def api_key():
    for line in CREDS.read_text().splitlines():
        if line.startswith(("api_key_readonly=", "api_key_ro=")):
            return line.split("=", 1)[1].strip()
    print("judge: no api_key_readonly in credentials", file=sys.stderr)
    sys.exit(2)


def fetch():
    req = urllib.request.Request(API, headers={"X-Api-Key": api_key()})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)["checks"]
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            # My access is broken — say exactly that, nothing about targets.
            print(f"judge: AUTH FAILURE (HTTP {e.code}) — the read-only key "
                  "was rotated or revoked; targets were NOT evaluated")
            sys.exit(4)
        print(f"judge: API error HTTP {e.code}; targets not evaluated")
        sys.exit(1)
    except Exception as e:
        print(f"judge: API unreachable ({e}); targets not evaluated")
        sys.exit(1)


def main():
    wanted = set(sys.argv[1:])
    current = {}
    for c in fetch():
        slug = c.get("slug") or c.get("name")
        if wanted and slug not in wanted:
            continue
        current[slug] = c.get("status")
    try:
        previous = json.loads(STATE.read_text())
    except Exception:
        previous = {}
    for slug, status in sorted(current.items()):
        if previous.get(slug) != status:
            print(f"judge: {slug}: {previous.get(slug, '(unseen)')} -> {status}")
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(current, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
