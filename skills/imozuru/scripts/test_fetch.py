"""
Regression tests for fetch.py download() — gzip Content-Encoding.

Issue: some servers return gzip without being asked (the DeepMind
blog is the known case; watch.py's fetch_final already decompresses).
download() used to return the compressed bytes untouched: short
enough to pass the length check, decoded downstream into replacement
characters and saved as an OK source.

Run: python3 -m pytest scripts/test_fetch.py -v
"""

import gzip
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

import fetch


class FakeHeaders:
    def __init__(self, values):
        self._values = values

    def get(self, name, default=""):
        return self._values.get(name, default)


class FakeResponse:
    def __init__(self, body, headers=None):
        self._body = body
        self.headers = FakeHeaders(headers or {})
        self.length = len(body)

    def read(self, n=-1):
        chunk = self._body if n is None or n < 0 else self._body[:n]
        self._body = self._body[len(chunk):]
        self.length = len(self._body)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeOpener:
    def __init__(self, response):
        self._response = response

    def open(self, req, timeout=None):
        return self._response


def download_with(response, url="https://example.com/page"):
    # The opener is stubbed, so nothing leaves the process; the URL
    # check still resolves the name and may refuse it on hosts whose
    # DNS maps public names into private ranges (this VM's egress
    # does). IMOZURU_ALLOW_PRIVATE is fetch.py's own escape hatch.
    env = patch.dict(os.environ, {"IMOZURU_ALLOW_PRIVATE": "1"})
    with env, patch.object(fetch, "_OPENER", FakeOpener(response)):
        return fetch.download(url)


TEXT = "原文のテキスト。DeepMind のブログのように、頼まなくても gzip で返る。".encode("utf-8")


class GzipDownloadTests(unittest.TestCase):
    def test_gzip_body_is_decompressed(self):
        res = FakeResponse(gzip.compress(TEXT), {"Content-Encoding": "gzip"})
        body, _ = download_with(res)
        self.assertEqual(body, TEXT)

    def test_x_gzip_body_is_decompressed(self):
        res = FakeResponse(gzip.compress(TEXT), {"Content-Encoding": "x-gzip"})
        body, _ = download_with(res)
        self.assertEqual(body, TEXT)

    def test_plain_body_is_untouched(self):
        res = FakeResponse(TEXT, {"Content-Type": "text/html"})
        body, _ = download_with(res)
        self.assertEqual(body, TEXT)

    def test_truncated_gzip_is_rejected(self):
        cut = gzip.compress(TEXT)[:10]
        res = FakeResponse(cut, {"Content-Encoding": "gzip"})
        with self.assertRaises(ValueError):
            download_with(res)

    def test_expanded_size_over_cap_is_rejected(self):
        res = FakeResponse(gzip.compress(b"a" * 4096), {"Content-Encoding": "gzip"})
        with patch.object(fetch, "MAX_BYTES", 1024):
            with self.assertRaises(ValueError):
                download_with(res)


if __name__ == "__main__":
    unittest.main()
