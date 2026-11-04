#!/usr/bin/env python3
"""OAuth2 PKCE setup for access to the Beeper Desktop API.
Usage: oauth_setup.py [scope]   (default "read"; pass "read write" for send access)
Registers a public client, waits for the browser consent redirect on a loopback
listener, exchanges the code, and stores everything in ~/.config/beeper/oauth.json
(mode 600). Token values are never printed — only key names, lengths, expiry."""
import base64, hashlib, json, os, secrets, sys, threading, time
import urllib.request, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE = "http://127.0.0.1:23373"
REDIRECT = "http://127.0.0.1:8765/callback"
STORE_DIR = os.path.expanduser("~/.config/beeper")
STORE = os.path.join(STORE_DIR, "oauth.json")

def post_json(url, data, form=False):
    if form:
        body = urllib.parse.urlencode(data).encode()
        ctype = "application/x-www-form-urlencoded"
    else:
        body = json.dumps(data).encode()
        ctype = "application/json"
    req = urllib.request.Request(url, data=body, headers={"Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except Exception:
            return e.code, {"error": "unparsable"}

def main():
    scope = sys.argv[1] if len(sys.argv) > 1 else "read"
    os.makedirs(STORE_DIR, exist_ok=True)
    try:
        os.chmod(STORE_DIR, 0o700)
    except OSError:
        pass
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)

    status, reg = post_json(BASE + "/oauth/register", {
        "client_name": os.environ.get("BEEPER_CLIENT_NAME", "Agent"),
        "redirect_uris": [REDIRECT],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "scope": scope,
        "token_endpoint_auth_method": "none",
    })
    print("register status:", status, "| keys:", sorted(reg.keys()), flush=True)
    if status not in (200, 201) or "client_id" not in reg:
        print("REGISTER FAILED:", json.dumps(reg)[:300], flush=True)
        sys.exit(1)
    client_id = reg["client_id"]

    result = {}
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.urlparse(self.path)
            if q.path == "/callback":
                params = urllib.parse.parse_qs(q.query)
                result.update({k: v[0] for k, v in params.items()})
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write("Authorization received. You can close this tab.".encode())
            else:
                self.send_response(404); self.end_headers()
        def log_message(self, *a):
            pass
    server = HTTPServer(("127.0.0.1", 8765), H)
    th = threading.Thread(target=server.serve_forever, daemon=True)
    th.start()

    auth_url = BASE + "/oauth/authorize?" + urllib.parse.urlencode({
        "response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT,
        "scope": scope, "state": state, "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    print("AUTH_URL:", auth_url, flush=True)
    print("waiting for consent redirect (up to 600s)...", flush=True)
    deadline = time.time() + 600
    while time.time() < deadline and "code" not in result and "error" not in result:
        time.sleep(1)
    server.shutdown()
    if "code" not in result:
        print("NO CODE RECEIVED:", json.dumps(result)[:200], flush=True)
        sys.exit(2)
    if result.get("state") != state:
        print("STATE MISMATCH", flush=True)
        sys.exit(3)

    form = {
        "grant_type": "authorization_code", "code": result["code"],
        "redirect_uri": REDIRECT, "client_id": client_id, "code_verifier": verifier,
    }
    if reg.get("client_secret"):
        form["client_secret"] = reg["client_secret"]
    status, tok = post_json(BASE + "/oauth/token", form, form=True)
    print("token status:", status, "| keys:", sorted(tok.keys()), flush=True)
    if status != 200 or "access_token" not in tok:
        print("TOKEN FAILED:", json.dumps(tok)[:300], flush=True)
        sys.exit(4)
    store = {"client": reg, "tokens": tok, "obtained_at": int(time.time())}
    fd = os.open(STORE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(store, f)
    print("stored:", STORE,
          "| access len:", len(tok["access_token"]),
          "| refresh present:", bool(tok.get("refresh_token")),
          "| expires_in:", tok.get("expires_in"), flush=True)

if __name__ == "__main__":
    main()
