#!/usr/bin/env python3
"""Minimal CDP driver for the Beeper renderer (127.0.0.1:9222).

Usage:
  cdp.py eval '<js expression>'     -> prints JSON result value
  cdp.py insert '<css selector>' '<text>'  -> focus element, Input.insertText
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.expanduser("~/.pylibs"))
import websocket  # websocket-client

CDP = "http://127.0.0.1:9222"


def page_ws_url() -> str:
    with urllib.request.urlopen(f"{CDP}/json", timeout=5) as r:
        targets = json.load(r)
    for t in targets:
        if t.get("type") == "page" and t.get("title") == "Beeper":
            return t["webSocketDebuggerUrl"]
    raise RuntimeError("Beeper page target not found")


class CDPClient:
    def __init__(self):
        self.ws = websocket.create_connection(page_ws_url(), timeout=15)
        self._id = 0

    def call(self, method, params=None):
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def eval(self, expr):
        res = self.call(
            "Runtime.evaluate",
            {"expression": expr, "returnByValue": True, "awaitPromise": True},
        )
        if res.get("exceptionDetails"):
            raise RuntimeError(str(res["exceptionDetails"])[:500])
        return res.get("result", {}).get("value")


def main():
    cmd = sys.argv[1]
    c = CDPClient()
    if cmd == "eval":
        print(json.dumps(c.eval(sys.argv[2]), ensure_ascii=False))
    elif cmd == "insert":
        selector, text = sys.argv[2], sys.argv[3]
        ok = c.eval(
            f"(() => {{ const el = document.querySelector({json.dumps(selector)});"
            f" if (!el) return false; el.focus(); return true; }})()"
        )
        if not ok:
            print("element not found")
            return 1
        c.call("Input.insertText", {"text": text})
        print("inserted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
