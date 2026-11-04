#!/usr/bin/env python3
"""beeper_liveness — keep Beeper Desktop alive in this VM.

Beeper dies on every VM replacement, and while it is down the
factory-watch hook is blind and the todo crons cannot read chats.
This check probes the local Desktop API; if it does not answer, it
relaunches Beeper via launch-beeper.sh (idempotent: a running Beeper
is left untouched) and polls until the API answers.

Prints exactly one JSON line:
  {"verdict": "alive"}       API answered on the first probe
  {"verdict": "relaunched"}  API was down, relaunch brought it back
  {"verdict": "down"}        still down after relaunch (exit 1)
Appends the same line to beeper-liveness.log next to this script.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
LOG = HERE / "beeper-liveness.log"
LAUNCH = HERE / "launch-beeper.sh"


def probe():
    try:
        import beeper_api
        beeper_api.get('/v1/chats', params={'limit': 1})
        return True
    except BaseException:  # beeper_api sys.exit()s on failure (2=unreachable, 3=auth)
        return False


def emit(verdict, code):
    line = json.dumps({"verdict": verdict, "ts": time.strftime('%Y-%m-%dT%H:%M:%S%z')})
    print(line)
    try:
        with open(LOG, 'a') as f:
            f.write(line + '\n')
    except Exception:
        pass
    return code


def main():
    if probe():
        return emit("alive", 0)
    # Fire the launcher detached and poll the API: the launcher itself
    # returns once Beeper is started (it backgrounds the app), but its
    # exit alone is not proof the API is up — the poll below is.
    try:
        launch_log = open(HERE / "beeper-launch.log", 'a')
        subprocess.Popen(['bash', str(LAUNCH)], stdout=launch_log,
                         stderr=launch_log, start_new_session=True)
    except Exception:
        pass
    for _ in range(18):  # up to ~90s for the app + API to come up
        time.sleep(5)
        if probe():
            return emit("relaunched", 0)
    return emit("down", 1)


if __name__ == "__main__":
    sys.exit(main())
