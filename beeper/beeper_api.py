#!/usr/bin/env python3
"""Helper for the Beeper Desktop API (used by the agent's automations).
Loads the OAuth token from ~/.config/beeper/oauth.json. Never prints the token.
Usage:
  beeper_api.py chats [--limit N]
  beeper_api.py messages <chatID> [--limit N]
  beeper_api.py search <query>
  beeper_api.py send <chatID> <text...>   (write scope; use only per the caller's rules)
Exit 3 + 'AUTH_EXPIRED' on stderr when the token is missing/expired/rejected
(current token: read+write, non-expiring 'Never', no refresh token — re-run
oauth_setup.py "read write" to replace it)."""
import json, os, sys, time
import urllib.request, urllib.parse, urllib.error

BASE = "http://127.0.0.1:23373"
STORE = os.path.expanduser("~/.config/beeper/oauth.json")

def token():
    try:
        d = json.load(open(STORE))
        tok = d["tokens"]
        exp = tok.get("expires_in")
        if exp and time.time() > d.get("obtained_at", 0) + exp - 600:
            raise ValueError("expired")
        return tok["access_token"]
    except Exception:
        print("AUTH_EXPIRED", file=sys.stderr)
        sys.exit(3)

def get(path, params=None):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token()})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("AUTH_EXPIRED", file=sys.stderr)
            sys.exit(3)
        print(f"HTTP {e.code} on {path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"UNREACHABLE: {e}", file=sys.stderr)
        sys.exit(2)

def post(path, payload):
    url = BASE + path
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Authorization": "Bearer " + token(),
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("AUTH_EXPIRED", file=sys.stderr)
            sys.exit(3)
        print(f"HTTP {e.code} on {path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"UNREACHABLE: {e}", file=sys.stderr)
        sys.exit(2)

def main():
    args = sys.argv[1:]
    limit = 30
    if "--limit" in args:
        i = args.index("--limit")
        limit = int(args[i + 1])
        del args[i:i + 2]
    cmd = args[0] if args else ""
    if cmd == "chats":
        d = get("/v1/chats", {"limit": limit})
        def pv_text(c):
            pv = c.get("preview")
            if isinstance(pv, dict):
                pv = pv.get("text") or json.dumps(pv, ensure_ascii=False)
            return (pv or "")[:120] if isinstance(pv, str) else str(pv)[:120]
        out = [{"id": c.get("id"), "title": c.get("title"), "type": c.get("type"),
                "unread": c.get("unreadCount"), "lastActivity": c.get("lastActivity"),
                "preview": pv_text(c)} for c in d.get("items", [])]
        print(json.dumps(out, ensure_ascii=False, indent=1))
    elif cmd == "messages" and len(args) > 1:
        d = get(f"/v1/chats/{urllib.parse.quote(args[1], safe='')}/messages", {"limit": limit})
        out = [{"id": m.get("id"), "sender": m.get("sender") or m.get("senderName"),
                "ts": m.get("timestamp") or m.get("ts"), "text": (m.get("text") or m.get("body") or "")[:500]}
               for m in d.get("items", [])]
        print(json.dumps(out, ensure_ascii=False, indent=1))
    elif cmd == "search" and len(args) > 1:
        d = get("/v1/search", {"query": " ".join(args[1:])})
        print(json.dumps(d, ensure_ascii=False, indent=1)[:6000])
    elif cmd == "send" and len(args) > 2:
        d = post(f"/v1/chats/{urllib.parse.quote(args[1], safe='')}/messages",
                 {"text": " ".join(args[2:])})
        print(json.dumps(d, ensure_ascii=False, indent=1)[:1000])
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(64)

if __name__ == "__main__":
    main()
