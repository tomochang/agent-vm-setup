#!/usr/bin/env python3
"""jpsearch.py <komachi|chiebukuro|anond|note> <query> [n] -> prints 'url<TAB>title' lines.

Uses each site's own search (no WebSearch budget). Written in the 2026-10-27 saiaku run.
"""
import html
import json
import re
import sys
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124 Safari/537.36"}
SEARCH_URL = {
    "komachi": "https://komachi.yomiuri.co.jp/search/?text={q}",
    "chiebukuro": "https://chiebukuro.yahoo.co.jp/search?p={q}",
    "anond": "https://anond.hatelabo.jp/search?word={q}",
    "note": "https://note.com/api/v3/searches?context=note&q={q}&size={n}",
}


def _text(fragment):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment)).strip()


def parse(site, body):
    """Turn one search result page (or note's JSON) into [(url, title)]."""
    out = []
    if site == "komachi":
        for m in re.finditer(r'href="(/topics/id/\d+/?)"[^>]*>(.*?)</a>', body, re.S):
            out.append(("https://komachi.yomiuri.co.jp" + m.group(1), _text(m.group(2))))
    elif site == "chiebukuro":
        pat = r'href="(https://detail\.chiebukuro\.yahoo\.co\.jp/qa/question_detail/q\d+)[^"]*"[^>]*>(.*?)</a>'
        for m in re.finditer(pat, body, re.S):
            out.append((m.group(1), _text(m.group(2))))
    elif site == "anond":
        for m in re.finditer(r'<h3><a href="/(\d{14})">(.*?)</a>', body, re.S):
            out.append(("https://anond.hatelabo.jp/" + m.group(1), _text(m.group(2))))
        if not out:
            for m in re.finditer(r'href="/(\d{14})"', body):
                out.append(("https://anond.hatelabo.jp/" + m.group(1), ""))
    elif site == "note":
        for c in json.loads(body)["data"]["notes"]["contents"]:
            out.append((f"https://note.com/{c['user']['urlname']}/n/{c['key']}", c["name"]))
    else:
        raise ValueError(f"unknown site: {site}")
    return out


def dedupe(rows, n):
    seen, kept = set(), []
    for url, title in rows:
        if url in seen:
            continue
        seen.add(url)
        kept.append((url, title))
        if len(kept) >= n:
            break
    return kept


def main(argv):
    site, query = argv[1], argv[2]
    n = int(argv[3]) if len(argv) > 3 else 15
    url = SEARCH_URL[site].format(q=urllib.parse.quote(query), n=n)
    body = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read()
    for u, title in dedupe(parse(site, body.decode("utf-8", "replace")), n):
        print(f"{u}\t{html.unescape(title)[:100]}")


if __name__ == "__main__":
    main(sys.argv)
