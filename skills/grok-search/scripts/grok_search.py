"""
grok_search.py — Grok API (xAI) を使ったX/Web検索クライアント

Usage (CLI):
    python3 grok_search.py x   "AI news today" [--json] [--domain-filter x.com]
    python3 grok_search.py web "latest Claude Code updates" [--json]
    python3 grok_search.py both "investment signals semiconductor" [--json]

Python API:
    from grok_search import GrokSearch
    client = GrokSearch()           # XAI_API_KEY from env
    result = client.search_x("AI news today")
    print(result.text)
    print(result.citations)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Optional requests import with urllib fallback shim
# ---------------------------------------------------------------------------
try:
    import requests as _req_lib

    def requests_post(url: str, *, headers: dict, json: dict, timeout: int) -> Any:
        return _req_lib.post(url, headers=headers, json=json, timeout=timeout)

    _requests_available = True
except ImportError:  # pragma: no cover
    import urllib.error
    import urllib.request

    _req_lib = None  # type: ignore[assignment]
    _requests_available = False

    class _FakeResponse:
        def __init__(self, data: bytes, status_code: int):
            self.status_code = status_code
            self._data = data
            self.text = data.decode()

        def json(self):
            return json.loads(self._data)

        def raise_for_status(self):
            if self.status_code >= 400:
                raise _FakeHTTPError(f"HTTP {self.status_code}")

    class _FakeHTTPError(Exception):
        pass

    def requests_post(url: str, *, headers: dict, json: dict, timeout: int) -> Any:  # type: ignore[misc]
        data = _json_module.dumps(json).encode()
        req = urllib.request.Request(url, data=data, headers={**headers, "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                return _FakeResponse(body, resp.status)
        except urllib.error.HTTPError as e:
            return _FakeResponse(e.read(), e.code)
        except urllib.error.URLError as e:
            if "timed out" in str(e).lower():
                raise GrokSearchTimeoutError("Request timed out") from None
            raise GrokSearchError(f"Network error: {type(e).__name__}") from None

# Keep a reference to the json module for the urllib path above
import json as _json_module  # noqa: E402 (already imported as json below)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class GrokSearchError(Exception):
    """Base exception for all Grok search errors."""


class GrokSearchRateLimitError(GrokSearchError):
    """Raised when the API returns HTTP 429."""


class GrokSearchTimeoutError(GrokSearchError):
    """Raised when the request times out."""


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class GrokSearchResult:
    text: str = ""
    citations: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "citations": self.citations,
            "tool_calls": self.tool_calls,
            "usage": self.usage,
        }


# ---------------------------------------------------------------------------
# GrokSearch client
# ---------------------------------------------------------------------------

_API_ENDPOINT = "https://api.x.ai/v1/responses"
_DEFAULT_MODEL = "grok-4-1-fast-non-reasoning"
_DEFAULT_TIMEOUT = 60
_TICKS_PER_USD = 1_000_000  # 1 tick = 1e-6 USD


class GrokSearch:
    """Client for xAI Grok API search capabilities."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = _DEFAULT_MODEL,
        timeout: int = _DEFAULT_TIMEOUT,
    ):
        resolved_key = api_key or os.environ.get("XAI_API_KEY", "")
        if not resolved_key:
            raise GrokSearchError(
                "API key not found. Set the XAI_API_KEY environment variable "
                "or pass api_key= to GrokSearch()."
            )
        self.api_key = resolved_key
        self.model = model
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Public search methods
    # ------------------------------------------------------------------

    def search_x(self, query: str, *, domain_filter: str | None = None) -> GrokSearchResult:
        """Search X/Twitter posts using x_search."""
        tools = [self._make_x_search_tool(domain_filter=domain_filter)]
        return self._call(query, tools)

    def search_web(self, query: str) -> GrokSearchResult:
        """Search the general web using web_search."""
        tools = [{"type": "web_search"}]
        return self._call(query, tools)

    def search_both(self, query: str, *, domain_filter: str | None = None) -> GrokSearchResult:
        """Search X and the web simultaneously."""
        tools = [
            self._make_x_search_tool(domain_filter=domain_filter),
            {"type": "web_search"},
        ]
        return self._call(query, tools)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_x_search_tool(self, *, domain_filter: str | None = None) -> dict:
        tool: dict[str, Any] = {"type": "x_search"}
        if domain_filter:
            tool["domain_filter"] = domain_filter
        return tool

    def _call(self, query: str, tools: list[dict]) -> GrokSearchResult:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "tools": tools,
            "input": query,
        }

        try:
            resp = requests_post(
                _API_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
        except GrokSearchTimeoutError:
            raise
        except GrokSearchError:
            raise
        except Exception as exc:
            # Absorb any exception type that mentions the API key string
            exc_type = type(exc).__name__
            # Check for timeout variants from requests
            if _requests_available:
                if isinstance(exc, _req_lib.Timeout):
                    raise GrokSearchTimeoutError("Request timed out") from None
                if isinstance(exc, _req_lib.RequestException):
                    raise GrokSearchError(f"Network error: {exc_type}") from None
            raise GrokSearchError(f"Unexpected error: {exc_type}") from None

        # Handle HTTP errors
        try:
            resp.raise_for_status()
        except Exception as exc:
            status = getattr(resp, "status_code", 0)
            if status == 429:
                raise GrokSearchRateLimitError(
                    f"Rate limit exceeded (HTTP 429)"
                ) from None
            raise GrokSearchError(
                f"API error (HTTP {status})"
            ) from None

        data = resp.json()
        return self._parse_response(data)

    def _parse_response(self, data: dict) -> GrokSearchResult:
        output = data.get("output", [])
        text_parts: list[str] = []
        citations: list[dict] = []
        tool_calls: list[dict] = []

        for item in output:
            item_type = item.get("type", "")

            if item_type == "message":
                for content_block in item.get("content", []):
                    if content_block.get("type") == "output_text":
                        text_parts.append(content_block.get("text", ""))
                        for ann in content_block.get("annotations", []):
                            if ann.get("type") == "url_citation":
                                citations.append({
                                    "url": ann.get("url", ""),
                                    "title": ann.get("title", ""),
                                    "start": ann.get("start_index"),
                                    "end": ann.get("end_index"),
                                })

            elif item_type in ("custom_tool_call", "tool_call"):
                raw_input = item.get("input", "{}")
                try:
                    parsed_input = json.loads(raw_input) if isinstance(raw_input, str) else raw_input
                except json.JSONDecodeError:
                    parsed_input = {}
                tool_calls.append({
                    "name": item.get("name", ""),
                    "query": parsed_input.get("query", ""),
                })

        usage_raw = data.get("usage", {})
        ticks = usage_raw.get("cost_in_usd_ticks", 0)
        usage = {
            "prompt_tokens": usage_raw.get("prompt_tokens", 0),
            "completion_tokens": usage_raw.get("completion_tokens", 0),
            "cost_usd": ticks / _TICKS_PER_USD,
        }

        return GrokSearchResult(
            text="\n".join(text_parts),
            citations=citations,
            tool_calls=tool_calls,
            usage=usage,
        )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Grok API search — X/Twitter and Web"
    )
    parser.add_argument(
        "mode",
        choices=["x", "web", "both"],
        help="Search mode: x (X/Twitter), web (general web), both (combined)",
    )
    parser.add_argument("query", help="Search query")
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output structured JSON",
    )
    parser.add_argument(
        "--domain-filter",
        default=None,
        metavar="DOMAIN",
        help="Filter X results to a specific domain (x_search mode only)",
    )
    args = parser.parse_args(argv)

    try:
        client = GrokSearch()
    except GrokSearchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        if args.mode == "x":
            result = client.search_x(args.query, domain_filter=args.domain_filter)
        elif args.mode == "web":
            result = client.search_web(args.query)
        else:
            result = client.search_both(args.query, domain_filter=args.domain_filter)
    except GrokSearchRateLimitError as exc:
        print(f"Rate limit: {exc}", file=sys.stderr)
        sys.exit(2)
    except GrokSearchTimeoutError as exc:
        print(f"Timeout: {exc}", file=sys.stderr)
        sys.exit(3)
    except GrokSearchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.output_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(result.text)
        if result.citations:
            print("\n--- Citations ---")
            for i, c in enumerate(result.citations, 1):
                title = c.get("title") or c.get("url", "")
                url = c.get("url", "")
                print(f"[{i}] {title} — {url}")
        if result.usage:
            cost = result.usage.get("cost_usd", 0)
            pt = result.usage.get("prompt_tokens", 0)
            ct = result.usage.get("completion_tokens", 0)
            print(f"\n[tokens: {pt}+{ct} | cost: ${cost:.4f}]", file=sys.stderr)


if __name__ == "__main__":
    main()
