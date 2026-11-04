#!/bin/bash
# Launch Beeper Desktop on a headless Linux VM (Xvfb + openbox + a11y bus),
# so agents can drive it over CDP (port 9222) and use its local API (23373).
#
# Environment knobs:
#   BEEPER_APP_DIR   extracted AppImage dir (default: ~/Applications/squashfs-root)
#   BEEPER_PROXY     proxy URL if the VM needs one (default: none).
#                    IMPORTANT: if your egress proxy rotates credentials per
#                    session, pass a credential-free URL that the proxy
#                    accepts unauthenticated, or leave unset. A credentialed
#                    URL captured at launch time goes stale (HTTP 407) and
#                    Beeper sign-in fails with a generic error.
# Every step is idempotent; safe to call from a health loop.
# NOTE on killing Beeper: never write `pkill -f beepertexts` in a shell
# you care about — the pattern matches your own command line and kills
# your shell too. Use the bracket form: pkill -f '[b]eepertexts'.
set -u
export DISPLAY=:99
APP_DIR="${BEEPER_APP_DIR:-$HOME/Applications/squashfs-root}"
PROXY="${BEEPER_PROXY:-}"
if [ -n "$PROXY" ]; then
  export http_proxy="$PROXY" https_proxy="$PROXY" HTTP_PROXY="$PROXY" HTTPS_PROXY="$PROXY"
fi

DIAG_DIR="$HOME/workspace/beeper-diag"
DBUS_ENV_FILE="$DIAG_DIR/dbus-session.env"
mkdir -p "$DIAG_DIR"

# Xvfb on :99
pgrep -f 'Xvfb :99' >/dev/null || (Xvfb :99 -screen 0 1280x800x24 >/dev/null 2>&1 &)
sleep 1

bus_alive() {
  [ -n "${DBUS_SESSION_BUS_ADDRESS:-}" ] || return 1
  gdbus call --timeout 2 --address "$DBUS_SESSION_BUS_ADDRESS" \
    --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus \
    --method org.freedesktop.DBus.ListNames >/dev/null 2>&1
}

# D-Bus session bus: reuse the persisted one while it is alive
if [ -f "$DBUS_ENV_FILE" ]; then
  # shellcheck disable=SC1090
  . "$DBUS_ENV_FILE"
fi
if ! bus_alive; then
  _bus_out=$(dbus-daemon --session --fork --print-address=1 --print-pid=1)
  DBUS_SESSION_BUS_ADDRESS=$(printf '%s\n' "$_bus_out" | sed -n '1p')
  DBUS_SESSION_BUS_PID=$(printf '%s\n' "$_bus_out" | sed -n '2p')
fi
export DBUS_SESSION_BUS_ADDRESS
umask 077
{
  printf "export DBUS_SESSION_BUS_ADDRESS='%s'\n" "$DBUS_SESSION_BUS_ADDRESS"
  printf "export DBUS_SESSION_BUS_PID='%s'\n" "${DBUS_SESSION_BUS_PID:-}"
} > "$DBUS_ENV_FILE"
chmod 600 "$DBUS_ENV_FILE" 2>/dev/null

# Enable accessibility on the bus (lets agent-desktop tooling see the UI)
gdbus call --timeout 5 --address "$DBUS_SESSION_BUS_ADDRESS" \
  --dest org.a11y.Bus --object-path /org/a11y/bus \
  --method org.freedesktop.DBus.Properties.Set org.a11y.Status IsEnabled '<true>' >/dev/null 2>&1

# Window manager on :99
pgrep -x openbox >/dev/null || (openbox >/dev/null 2>&1 &)
sleep 1

# Beeper itself: if it is already up, leave it alone
if pgrep -f 'squashfs-root/beepertexts' >/dev/null; then
  echo "launch-beeper: already running; bus/WM/a11y ensured, leaving it up"
  exit 0
fi
cd "$APP_DIR" || exit 1
if [ -n "$PROXY" ]; then
  nohup ./beepertexts --no-sandbox --force-renderer-accessibility \
    --remote-debugging-port=9222 --remote-allow-origins=* \
    --proxy-server="$PROXY" >/tmp/beeper.log 2>&1 &
else
  nohup ./beepertexts --no-sandbox --force-renderer-accessibility \
    --remote-debugging-port=9222 --remote-allow-origins=* >/tmp/beeper.log 2>&1 &
fi
echo "launch-beeper: started pid $!"
