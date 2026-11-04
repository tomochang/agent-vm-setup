#!/usr/bin/env python3
"""Scrapling fetch script — called by the agent via exec."""

import sys
import json
import argparse

from scrapling.fetchers import Fetcher, StealthyFetcher, DynamicFetcher


def fetch(url: str, selector: str = None, mode: str = "auto"):
    """Fetch a URL and extract content."""
    page = None

    if mode == "stealth":
        page = StealthyFetcher.fetch(url, headless=True, network_idle=True)
    elif mode == "dynamic":
        page = DynamicFetcher.fetch(url, headless=True, network_idle=True)
    elif mode == "fast":
        page = Fetcher.get(url)
    else:  # auto
        page = Fetcher.get(url)
        # Fallback: if content looks empty, retry with StealthyFetcher
        text = page.text.strip() if page.text else ""
        if page.status != 200 or len(text) < 100:
            print("[auto] Fetcher returned insufficient content, retrying with StealthyFetcher...", file=sys.stderr)
            page = StealthyFetcher.fetch(url, headless=True, network_idle=True)

    result = {
        "url": url,
        "status": page.status,
        "mode": mode,
    }

    if selector:
        # Extract specific elements
        elements = page.css(f'{selector}::text').getall()
        if not elements:
            elements = page.css(selector).getall()
        result["selector"] = selector
        result["count"] = len(elements)
        result["data"] = elements[:50]  # Limit to 50 items
    else:
        # Auto-extract: title, headings, main text
        title = page.css('title::text').get() or ""
        h1s = page.css('h1::text').getall()
        h2s = page.css('h2::text').getall()
        h3s = page.css('h3::text').getall()
        paragraphs = page.css('p::text').getall()

        result["title"] = title.strip()
        result["headings"] = {
            "h1": h1s[:10],
            "h2": h2s[:20],
            "h3": h3s[:20],
        }
        result["paragraphs"] = paragraphs[:30]
        result["links_count"] = len(page.css('a::attr(href)').getall())

    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Scrapling fetch")
    parser.add_argument("url", help="URL to fetch")
    parser.add_argument("selector", nargs="?", default=None, help="CSS selector")
    parser.add_argument("--mode", choices=["auto", "fast", "stealth", "dynamic"], default="auto")
    args = parser.parse_args()
    fetch(args.url, args.selector, args.mode)


if __name__ == "__main__":
    main()
