"""
Tests for grok_search.py — TDD first, implementation follows.
Run: cd /workspace/skills/grok-search && python3 -m pytest scripts/test_grok_search.py -v
"""
import json
import os
import sys
import unittest
from io import StringIO
from unittest.mock import MagicMock, patch

# Allow importing sibling module
sys.path.insert(0, os.path.dirname(__file__))

# ---------------------------------------------------------------------------
# Shared mock response fixture
# ---------------------------------------------------------------------------

MOCK_RESPONSE_JSON = {
    "output": [
        {
            "type": "custom_tool_call",
            "name": "x_semantic_search",
            "input": json.dumps({"query": "test"}),
            "status": "completed",
        },
        {
            "type": "message",
            "content": [
                {
                    "type": "output_text",
                    "text": "Result text",
                    "annotations": [
                        {
                            "type": "url_citation",
                            "url": "https://x.com/user/status/123",
                            "title": "Test Post",
                            "start_index": 0,
                            "end_index": 10,
                        }
                    ],
                }
            ],
        },
    ],
    "usage": {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "cost_in_usd_ticks": 150000,
    },
}

MOCK_RESPONSE_WEB_JSON = {
    "output": [
        {
            "type": "custom_tool_call",
            "name": "web_search",
            "input": json.dumps({"query": "test web"}),
            "status": "completed",
        },
        {
            "type": "message",
            "content": [
                {
                    "type": "output_text",
                    "text": "Web result text",
                    "annotations": [
                        {
                            "type": "url_citation",
                            "url": "https://example.com/article",
                            "title": "Example Article",
                        }
                    ],
                }
            ],
        },
    ],
    "usage": {
        "prompt_tokens": 80,
        "completion_tokens": 40,
        "cost_in_usd_ticks": 100000,
    },
}

MOCK_RESPONSE_BOTH_JSON = {
    "output": [
        {
            "type": "custom_tool_call",
            "name": "x_semantic_search",
            "input": json.dumps({"query": "both test"}),
            "status": "completed",
        },
        {
            "type": "custom_tool_call",
            "name": "web_search",
            "input": json.dumps({"query": "both test"}),
            "status": "completed",
        },
        {
            "type": "message",
            "content": [
                {
                    "type": "output_text",
                    "text": "Combined result",
                    "annotations": [
                        {
                            "type": "url_citation",
                            "url": "https://x.com/post/1",
                            "title": "X Post",
                        },
                        {
                            "type": "url_citation",
                            "url": "https://news.example.com/story",
                            "title": "News Story",
                        },
                    ],
                }
            ],
        },
    ],
    "usage": {
        "prompt_tokens": 120,
        "completion_tokens": 60,
        "cost_in_usd_ticks": 200000,
    },
}

MOCK_EMPTY_JSON = {
    "output": [],
    "usage": {"prompt_tokens": 10, "completion_tokens": 0, "cost_in_usd_ticks": 0},
}


def _make_mock_response(data: dict, status_code: int = 200):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = data
    mock_resp.text = json.dumps(data)
    if status_code >= 400:
        from requests import HTTPError
        mock_resp.raise_for_status.side_effect = HTTPError(
            f"HTTP {status_code}", response=mock_resp
        )
    else:
        mock_resp.raise_for_status.return_value = None
    return mock_resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGrokSearchX(unittest.TestCase):
    """test_search_x — x_searchモード正常系"""

    @patch.dict(os.environ, {"XAI_API_KEY": "xai-test-key"})
    @patch("grok_search.requests_post")
    def test_search_x(self, mock_post):
        mock_post.return_value = _make_mock_response(MOCK_RESPONSE_JSON)
        from grok_search import GrokSearch
        client = GrokSearch()
        result = client.search_x("AI news today")

        self.assertEqual(result.text, "Result text")
        # Verify x_search tool was used in the request
        call_args = mock_post.call_args
        body = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
        tool_types = [t["type"] for t in body.get("tools", [])]
        self.assertIn("x_search", tool_types)
        self.assertNotIn("web_search", tool_types)


class TestGrokSearchWeb(unittest.TestCase):
    """test_search_web — web_searchモード正常系"""

    @patch.dict(os.environ, {"XAI_API_KEY": "xai-test-key"})
    @patch("grok_search.requests_post")
    def test_search_web(self, mock_post):
        mock_post.return_value = _make_mock_response(MOCK_RESPONSE_WEB_JSON)
        from grok_search import GrokSearch
        client = GrokSearch()
        result = client.search_web("Claude Code updates")

        self.assertEqual(result.text, "Web result text")
        call_args = mock_post.call_args
        body = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
        tool_types = [t["type"] for t in body.get("tools", [])]
        self.assertIn("web_search", tool_types)
        self.assertNotIn("x_search", tool_types)


class TestGrokSearchBoth(unittest.TestCase):
    """test_search_both — 統合モード正常系"""

    @patch.dict(os.environ, {"XAI_API_KEY": "xai-test-key"})
    @patch("grok_search.requests_post")
    def test_search_both(self, mock_post):
        mock_post.return_value = _make_mock_response(MOCK_RESPONSE_BOTH_JSON)
        from grok_search import GrokSearch
        client = GrokSearch()
        result = client.search_both("investment signals semiconductor")

        self.assertEqual(result.text, "Combined result")
        self.assertEqual(len(result.citations), 2)
        call_args = mock_post.call_args
        body = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
        tool_types = [t["type"] for t in body.get("tools", [])]
        self.assertIn("x_search", tool_types)
        self.assertIn("web_search", tool_types)


class TestParseCitations(unittest.TestCase):
    """test_parse_citations — annotationsから引用を正しく抽出"""

    @patch.dict(os.environ, {"XAI_API_KEY": "xai-test-key"})
    @patch("grok_search.requests_post")
    def test_parse_citations(self, mock_post):
        mock_post.return_value = _make_mock_response(MOCK_RESPONSE_JSON)
        from grok_search import GrokSearch
        client = GrokSearch()
        result = client.search_x("test")

        self.assertEqual(len(result.citations), 1)
        citation = result.citations[0]
        self.assertEqual(citation["url"], "https://x.com/user/status/123")
        self.assertEqual(citation["title"], "Test Post")
        self.assertIn("start", citation)
        self.assertIn("end", citation)

    @patch.dict(os.environ, {"XAI_API_KEY": "xai-test-key"})
    @patch("grok_search.requests_post")
    def test_parse_citations_non_url_annotations_ignored(self, mock_post):
        """url_citation以外のアノテーションは無視される"""
        data = dict(MOCK_RESPONSE_JSON)
        data["output"] = [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": "text",
                        "annotations": [
                            {"type": "other_type", "url": "https://ignored.com"},
                            {"type": "url_citation", "url": "https://kept.com", "title": "kept"},
                        ],
                    }
                ],
            }
        ]
        mock_post.return_value = _make_mock_response(data)
        from grok_search import GrokSearch
        client = GrokSearch()
        result = client.search_x("test")
        self.assertEqual(len(result.citations), 1)
        self.assertEqual(result.citations[0]["url"], "https://kept.com")


class TestParseToolCalls(unittest.TestCase):
    """test_parse_tool_calls — ツール呼び出し情報の抽出"""

    @patch.dict(os.environ, {"XAI_API_KEY": "xai-test-key"})
    @patch("grok_search.requests_post")
    def test_parse_tool_calls(self, mock_post):
        mock_post.return_value = _make_mock_response(MOCK_RESPONSE_JSON)
        from grok_search import GrokSearch
        client = GrokSearch()
        result = client.search_x("test")

        self.assertEqual(len(result.tool_calls), 1)
        tc = result.tool_calls[0]
        self.assertEqual(tc["name"], "x_semantic_search")
        self.assertEqual(tc["query"], "test")

    @patch.dict(os.environ, {"XAI_API_KEY": "xai-test-key"})
    @patch("grok_search.requests_post")
    def test_parse_tool_calls_both(self, mock_post):
        mock_post.return_value = _make_mock_response(MOCK_RESPONSE_BOTH_JSON)
        from grok_search import GrokSearch
        client = GrokSearch()
        result = client.search_both("both test")
        self.assertEqual(len(result.tool_calls), 2)
        names = {tc["name"] for tc in result.tool_calls}
        self.assertIn("x_semantic_search", names)
        self.assertIn("web_search", names)


class TestCostCalculation(unittest.TestCase):
    """test_cost_calculation — cost_in_usd_ticks → USD変換"""

    @patch.dict(os.environ, {"XAI_API_KEY": "xai-test-key"})
    @patch("grok_search.requests_post")
    def test_cost_calculation(self, mock_post):
        mock_post.return_value = _make_mock_response(MOCK_RESPONSE_JSON)
        from grok_search import GrokSearch
        client = GrokSearch()
        result = client.search_x("test")

        # 150000 ticks * 1e-6 = 0.15 USD
        self.assertAlmostEqual(result.usage["cost_usd"], 0.15, places=6)
        self.assertEqual(result.usage["prompt_tokens"], 100)
        self.assertEqual(result.usage["completion_tokens"], 50)

    @patch.dict(os.environ, {"XAI_API_KEY": "xai-test-key"})
    @patch("grok_search.requests_post")
    def test_cost_calculation_zero(self, mock_post):
        mock_post.return_value = _make_mock_response(MOCK_EMPTY_JSON)
        from grok_search import GrokSearch
        client = GrokSearch()
        result = client.search_x("test")
        self.assertAlmostEqual(result.usage["cost_usd"], 0.0, places=6)


class TestMissingApiKey(unittest.TestCase):
    """test_missing_api_key — キー未設定時のエラー"""

    def test_missing_api_key_raises(self):
        from grok_search import GrokSearch, GrokSearchError
        env = {k: v for k, v in os.environ.items() if k != "XAI_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(GrokSearchError) as ctx:
                GrokSearch()
            self.assertIn("XAI_API_KEY", str(ctx.exception))

    def test_explicit_api_key_overrides_env(self):
        env = {k: v for k, v in os.environ.items() if k != "XAI_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            from grok_search import GrokSearch
            # Should not raise when key is provided explicitly
            client = GrokSearch(api_key="xai-explicit-key")
            self.assertEqual(client.api_key, "xai-explicit-key")


class TestApiErrorHandling(unittest.TestCase):
    """test_api_error_handling — 4xx/5xx レスポンス"""

    @patch.dict(os.environ, {"XAI_API_KEY": "xai-test-key"})
    @patch("grok_search.requests_post")
    def test_api_error_4xx(self, mock_post):
        mock_post.return_value = _make_mock_response({"error": "bad request"}, 400)
        from grok_search import GrokSearch, GrokSearchError
        client = GrokSearch()
        with self.assertRaises(GrokSearchError):
            client.search_x("test")

    @patch.dict(os.environ, {"XAI_API_KEY": "xai-test-key"})
    @patch("grok_search.requests_post")
    def test_api_error_5xx(self, mock_post):
        mock_post.return_value = _make_mock_response({"error": "server error"}, 500)
        from grok_search import GrokSearch, GrokSearchError
        client = GrokSearch()
        with self.assertRaises(GrokSearchError):
            client.search_x("test")

    @patch.dict(os.environ, {"XAI_API_KEY": "xai-test-key"})
    @patch("grok_search.requests_post")
    def test_api_error_429_rate_limit(self, mock_post):
        mock_post.return_value = _make_mock_response({"error": "rate limit"}, 429)
        from grok_search import GrokSearch, GrokSearchRateLimitError
        client = GrokSearch()
        with self.assertRaises(GrokSearchRateLimitError):
            client.search_x("test")


class TestTimeoutHandling(unittest.TestCase):
    """test_timeout_handling — タイムアウト時のエラー"""

    @patch.dict(os.environ, {"XAI_API_KEY": "xai-test-key"})
    @patch("grok_search.requests_post")
    def test_timeout_handling(self, mock_post):
        import requests as req_lib
        mock_post.side_effect = req_lib.Timeout("Request timed out")
        from grok_search import GrokSearch, GrokSearchTimeoutError
        client = GrokSearch()
        with self.assertRaises(GrokSearchTimeoutError):
            client.search_x("test")

    @patch.dict(os.environ, {"XAI_API_KEY": "xai-test-key"})
    @patch("grok_search.requests_post")
    def test_default_timeout_is_60(self, mock_post):
        mock_post.return_value = _make_mock_response(MOCK_RESPONSE_JSON)
        from grok_search import GrokSearch
        client = GrokSearch()
        client.search_x("test")
        call_kwargs = mock_post.call_args[1]
        self.assertEqual(call_kwargs.get("timeout"), 60)


class TestApiKeyNotInError(unittest.TestCase):
    """test_api_key_not_in_error — エラーメッセージにAPIキーが含まれないこと"""

    @patch.dict(os.environ, {"XAI_API_KEY": "xai-super-secret-key-12345"})
    @patch("grok_search.requests_post")
    def test_api_key_not_in_error(self, mock_post):
        mock_post.return_value = _make_mock_response({"error": "bad request"}, 400)
        from grok_search import GrokSearch, GrokSearchError
        client = GrokSearch()
        try:
            client.search_x("test")
        except GrokSearchError as e:
            self.assertNotIn("xai-super-secret-key-12345", str(e))
            self.assertNotIn("xai-super-secret-key-12345", repr(e))

    @patch.dict(os.environ, {"XAI_API_KEY": "xai-super-secret-key-12345"})
    @patch("grok_search.requests_post")
    def test_api_key_not_in_timeout_error(self, mock_post):
        import requests as req_lib
        mock_post.side_effect = req_lib.Timeout("timeout")
        from grok_search import GrokSearch, GrokSearchTimeoutError
        client = GrokSearch()
        try:
            client.search_x("test")
        except GrokSearchTimeoutError as e:
            self.assertNotIn("xai-super-secret-key-12345", str(e))


class TestCliXMode(unittest.TestCase):
    """test_cli_x_mode — CLIのxモード"""

    @patch.dict(os.environ, {"XAI_API_KEY": "xai-test-key"})
    @patch("grok_search.requests_post")
    def test_cli_x_mode(self, mock_post):
        mock_post.return_value = _make_mock_response(MOCK_RESPONSE_JSON)
        import grok_search
        with patch("sys.argv", ["grok_search.py", "x", "AI news today"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_out:
                grok_search.main()
                output = mock_out.getvalue()
        self.assertIn("Result text", output)

    @patch.dict(os.environ, {"XAI_API_KEY": "xai-test-key"})
    @patch("grok_search.requests_post")
    def test_cli_web_mode(self, mock_post):
        mock_post.return_value = _make_mock_response(MOCK_RESPONSE_WEB_JSON)
        import grok_search
        with patch("sys.argv", ["grok_search.py", "web", "Claude updates"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_out:
                grok_search.main()
                output = mock_out.getvalue()
        self.assertIn("Web result text", output)


class TestCliJsonOutput(unittest.TestCase):
    """test_cli_json_output — CLI --json出力"""

    @patch.dict(os.environ, {"XAI_API_KEY": "xai-test-key"})
    @patch("grok_search.requests_post")
    def test_cli_json_output(self, mock_post):
        mock_post.return_value = _make_mock_response(MOCK_RESPONSE_JSON)
        import grok_search
        with patch("sys.argv", ["grok_search.py", "x", "AI news", "--json"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_out:
                grok_search.main()
                output = mock_out.getvalue()
        parsed = json.loads(output)
        self.assertIn("text", parsed)
        self.assertIn("citations", parsed)
        self.assertIn("usage", parsed)
        self.assertIn("tool_calls", parsed)
        self.assertEqual(parsed["text"], "Result text")

    @patch.dict(os.environ, {"XAI_API_KEY": "xai-test-key"})
    @patch("grok_search.requests_post")
    def test_cli_domain_filter(self, mock_post):
        mock_post.return_value = _make_mock_response(MOCK_RESPONSE_JSON)
        import grok_search
        with patch("sys.argv", ["grok_search.py", "x", "NVDA earnings", "--domain-filter", "x.com"]):
            with patch("sys.stdout", new_callable=StringIO):
                grok_search.main()
        call_args = mock_post.call_args
        body = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
        # domain filter should be reflected somewhere in the request
        tools = body.get("tools", [])
        x_tool = next((t for t in tools if t["type"] == "x_search"), None)
        self.assertIsNotNone(x_tool)


class TestEmptyResponse(unittest.TestCase):
    """test_empty_response — 空レスポンスのハンドリング"""

    @patch.dict(os.environ, {"XAI_API_KEY": "xai-test-key"})
    @patch("grok_search.requests_post")
    def test_empty_response(self, mock_post):
        mock_post.return_value = _make_mock_response(MOCK_EMPTY_JSON)
        from grok_search import GrokSearch
        client = GrokSearch()
        result = client.search_x("test")
        self.assertEqual(result.text, "")
        self.assertEqual(result.citations, [])
        self.assertEqual(result.tool_calls, [])
        self.assertAlmostEqual(result.usage["cost_usd"], 0.0)

    @patch.dict(os.environ, {"XAI_API_KEY": "xai-test-key"})
    @patch("grok_search.requests_post")
    def test_message_with_no_annotations(self, mock_post):
        data = {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "no citations here"}],
                }
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "cost_in_usd_ticks": 8000},
        }
        mock_post.return_value = _make_mock_response(data)
        from grok_search import GrokSearch
        client = GrokSearch()
        result = client.search_x("test")
        self.assertEqual(result.text, "no citations here")
        self.assertEqual(result.citations, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
