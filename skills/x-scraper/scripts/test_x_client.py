"""
x_client.py のテストスイート (TDD)
====================================
モックを使ってX API v2の各エンドポイントと
エラーハンドリングを検証する。
"""

import json
import sys
import os
import unittest
from unittest.mock import MagicMock, patch, call

# テスト対象モジュールをパスに追加
sys.path.insert(0, os.path.dirname(__file__))

from x_client import (
    XClient,
    XClientError,
    MissingTokenError,
    RateLimitError,
    APIError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status_code: int, body, headers: dict = None):
    """requests.Response モックを生成"""
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {}
    if isinstance(body, (dict, list)):
        resp.json.return_value = body
        resp.text = json.dumps(body)
    else:
        resp.json.side_effect = ValueError("no json")
        resp.text = str(body)
    return resp


SAMPLE_TWEETS = {
    "data": [
        {
            "id": "111111111111111111",
            "text": "Hello #Python world!",
            "created_at": "2024-01-01T00:00:00.000Z",
            "author_id": "12345",
            "public_metrics": {
                "like_count": 42,
                "retweet_count": 7,
                "reply_count": 3,
                "quote_count": 1,
            },
        },
        {
            "id": "222222222222222222",
            "text": "Another tweet about Python",
            "created_at": "2024-01-01T01:00:00.000Z",
            "author_id": "67890",
            "public_metrics": {
                "like_count": 10,
                "retweet_count": 2,
                "reply_count": 0,
                "quote_count": 0,
            },
        },
    ],
    "meta": {"newest_id": "222222222222222222", "oldest_id": "111111111111111111", "result_count": 2},
}

SAMPLE_USER = {
    "data": {
        "id": "12345",
        "name": "Test User",
        "username": "testuser",
        "description": "A test user account",
        "public_metrics": {
            "followers_count": 1000,
            "following_count": 500,
            "tweet_count": 3000,
            "listed_count": 50,
        },
        "created_at": "2010-01-01T00:00:00.000Z",
        "verified": False,
    }
}

SAMPLE_TRENDS = [
    {
        "trends": [
            {"name": "#Python", "tweet_volume": 50000, "url": "https://twitter.com/search?q=%23Python"},
            {"name": "#AI", "tweet_volume": 120000, "url": "https://twitter.com/search?q=%23AI"},
            {"name": "OpenAI", "tweet_volume": None, "url": "https://twitter.com/search?q=OpenAI"},
        ],
        "as_of": "2024-01-01T00:00:00Z",
        "locations": [{"name": "Japan", "woeid": 23424856}],
    }
]

SAMPLE_TWEET_DETAIL = {
    "data": {
        "id": "111111111111111111",
        "text": "Hello #Python world!",
        "created_at": "2024-01-01T00:00:00.000Z",
        "author_id": "12345",
        "lang": "en",
        "public_metrics": {
            "like_count": 42,
            "retweet_count": 7,
            "reply_count": 3,
            "quote_count": 1,
            "impression_count": 9999,
        },
        "entities": {
            "hashtags": [{"tag": "Python"}],
        },
    }
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestXClient(unittest.TestCase):

    def _make_client(self, token="test_bearer_token_dummy"):
        """テスト用クライアント生成（環境変数不要）"""
        return XClient(bearer_token=token)

    # ------------------------------------------------------------------
    # test_missing_token
    # ------------------------------------------------------------------
    def test_missing_token(self):
        """Bearer Token未設定時に MissingTokenError が発生すること"""
        with patch.dict(os.environ, {}, clear=True):
            # 環境変数から X_BEARER_TOKEN を除去
            env = {k: v for k, v in os.environ.items() if k != "X_BEARER_TOKEN"}
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaises(MissingTokenError) as ctx:
                    XClient()
                # エラーメッセージに取得手順が含まれること
                self.assertIn("developer.twitter.com", str(ctx.exception))
                self.assertIn("X_BEARER_TOKEN", str(ctx.exception))

    def test_missing_token_env_set(self):
        """環境変数 X_BEARER_TOKEN が設定されていればインスタンス化できること"""
        with patch.dict(os.environ, {"X_BEARER_TOKEN": "env_token_xyz"}):
            client = XClient()
            self.assertIsNotNone(client)

    # ------------------------------------------------------------------
    # test_search_tweets
    # ------------------------------------------------------------------
    def test_search_tweets(self):
        """正常なツイート検索レスポンスのパース"""
        client = self._make_client()
        mock_resp = _make_response(200, SAMPLE_TWEETS)

        with patch.object(client.session, "request", return_value=mock_resp) as mock_req:
            result = client.search_tweets("Python", max_results=10)

        # 正しいエンドポイントにリクエストされること
        call_args = mock_req.call_args
        self.assertIn("/tweets/search/recent", call_args[0][1])

        # パラメータ確認
        params = call_args[1]["params"]
        self.assertEqual(params["query"], "Python")
        self.assertEqual(params["max_results"], 10)

        # レスポンス構造確認
        self.assertIn("data", result)
        self.assertEqual(len(result["data"]), 2)
        self.assertEqual(result["data"][0]["id"], "111111111111111111")
        self.assertEqual(result["data"][0]["public_metrics"]["like_count"], 42)

    def test_search_tweets_max_results_clamped(self):
        """max_results が 10〜100 にクランプされること"""
        client = self._make_client()
        mock_resp = _make_response(200, SAMPLE_TWEETS)

        with patch.object(client.session, "request", return_value=mock_resp) as mock_req:
            # 5 → 10 にクランプ
            client.search_tweets("test", max_results=5)
            params = mock_req.call_args[1]["params"]
            self.assertEqual(params["max_results"], 10)

        with patch.object(client.session, "request", return_value=mock_resp) as mock_req:
            # 200 → 100 にクランプ
            client.search_tweets("test", max_results=200)
            params = mock_req.call_args[1]["params"]
            self.assertEqual(params["max_results"], 100)

    # ------------------------------------------------------------------
    # test_search_rate_limited
    # ------------------------------------------------------------------
    def test_search_rate_limited(self):
        """429レスポンス時にRetry-Afterを読んで待機・リトライすること"""
        client = self._make_client(token="limited_token")
        client.max_retries = 2

        rate_limit_resp = _make_response(
            429,
            {"title": "Too Many Requests"},
            headers={"Retry-After": "1"},
        )
        success_resp = _make_response(200, SAMPLE_TWEETS)

        # 1回目: 429, 2回目: 200
        with patch.object(client.session, "request", side_effect=[rate_limit_resp, success_resp]):
            with patch("time.sleep") as mock_sleep:
                result = client.search_tweets("test")

        # sleep が Retry-After の秒数で呼ばれること
        mock_sleep.assert_called_once_with(1)
        self.assertIn("data", result)

    def test_search_rate_limited_exhausted(self):
        """リトライ上限を超えたら RateLimitError を投げること"""
        client = self._make_client()
        client.max_retries = 1

        rate_limit_resp = _make_response(
            429,
            {"title": "Too Many Requests"},
            headers={"Retry-After": "1"},
        )

        with patch.object(client.session, "request", return_value=rate_limit_resp):
            with patch("time.sleep"):
                with self.assertRaises(RateLimitError):
                    client.search_tweets("test")

    # ------------------------------------------------------------------
    # test_user_lookup
    # ------------------------------------------------------------------
    def test_user_lookup(self):
        """ユーザー情報取得の正常動作"""
        client = self._make_client()
        mock_resp = _make_response(200, SAMPLE_USER)

        with patch.object(client.session, "request", return_value=mock_resp) as mock_req:
            result = client.get_user("testuser")

        # 正しいエンドポイント
        call_url = mock_req.call_args[0][1]
        self.assertIn("/users/by/username/testuser", call_url)

        # レスポンス確認
        self.assertIn("data", result)
        user = result["data"]
        self.assertEqual(user["username"], "testuser")
        self.assertEqual(user["public_metrics"]["followers_count"], 1000)
        self.assertEqual(user["public_metrics"]["tweet_count"], 3000)

    # ------------------------------------------------------------------
    # test_trends
    # ------------------------------------------------------------------
    def test_trends(self):
        """トレンド取得の正常動作"""
        client = self._make_client()
        mock_resp = _make_response(200, SAMPLE_TRENDS)

        with patch.object(client.session, "request", return_value=mock_resp) as mock_req:
            result = client.get_trends(woeid=23424856)

        # v1.1 エンドポイントを使うこと
        call_url = mock_req.call_args[0][1]
        self.assertIn("trends/place.json", call_url)

        # WOEID パラメータ
        params = mock_req.call_args[1]["params"]
        self.assertEqual(params["id"], 23424856)

        # レスポンス確認
        self.assertIsInstance(result, list)
        self.assertEqual(len(result[0]["trends"]), 3)
        self.assertEqual(result[0]["trends"][0]["name"], "#Python")

    # ------------------------------------------------------------------
    # test_tweet_detail
    # ------------------------------------------------------------------
    def test_tweet_detail(self):
        """ツイート詳細取得の正常動作"""
        client = self._make_client()
        mock_resp = _make_response(200, SAMPLE_TWEET_DETAIL)
        tweet_id = "111111111111111111"

        with patch.object(client.session, "request", return_value=mock_resp) as mock_req:
            result = client.get_tweet(tweet_id)

        # エンドポイント確認
        call_url = mock_req.call_args[0][1]
        self.assertIn(f"/tweets/{tweet_id}", call_url)

        # エンゲージメント指標確認
        tweet = result["data"]
        self.assertEqual(tweet["id"], tweet_id)
        self.assertEqual(tweet["public_metrics"]["impression_count"], 9999)
        self.assertEqual(tweet["public_metrics"]["like_count"], 42)
        self.assertIn("entities", tweet)

    # ------------------------------------------------------------------
    # test_error_handling
    # ------------------------------------------------------------------
    def test_error_handling_404(self):
        """404エラー時に APIError が発生すること"""
        client = self._make_client()
        mock_resp = _make_response(
            404,
            {"title": "Not Found", "detail": "User not found"},
        )

        with patch.object(client.session, "request", return_value=mock_resp):
            with self.assertRaises(APIError) as ctx:
                client.get_user("nonexistent_user_xyz")

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("404", str(ctx.exception))

    def test_error_handling_403(self):
        """403エラー時に APIError が発生すること"""
        client = self._make_client()
        mock_resp = _make_response(
            403,
            {"title": "Forbidden", "detail": "Access level insufficient"},
        )

        with patch.object(client.session, "request", return_value=mock_resp):
            with self.assertRaises(APIError) as ctx:
                client.search_tweets("test")

        self.assertEqual(ctx.exception.status_code, 403)

    def test_error_handling_500(self):
        """500エラー時に APIError が発生すること"""
        client = self._make_client()
        mock_resp = _make_response(500, "Internal Server Error")

        with patch.object(client.session, "request", return_value=mock_resp):
            with self.assertRaises(APIError) as ctx:
                client.get_tweet("12345")

        self.assertEqual(ctx.exception.status_code, 500)

    def test_error_handling_network(self):
        """ネットワークエラー時に XClientError が発生すること"""
        import requests as req_lib
        client = self._make_client()

        with patch.object(client.session, "request", side_effect=req_lib.ConnectionError("connection refused")):
            with self.assertRaises(XClientError):
                client.search_tweets("test")

    # ------------------------------------------------------------------
    # Security: token はエラーメッセージに含まれないこと
    # ------------------------------------------------------------------
    def test_token_not_in_missing_token_error(self):
        """MissingTokenError メッセージにトークン値が含まれないこと"""
        with patch.dict(os.environ, {}, clear=True):
            env = {k: v for k, v in os.environ.items() if k != "X_BEARER_TOKEN"}
            with patch.dict(os.environ, env, clear=True):
                try:
                    XClient()
                except MissingTokenError as e:
                    # "X_BEARER_TOKEN" という変数名は含んでよいが、実際のトークン値は含まれない
                    msg = str(e)
                    self.assertNotIn("sk-", msg)  # トークン形式の文字列ではない

    def test_token_not_in_api_error(self):
        """APIError メッセージにトークンが含まれないこと"""
        secret_token = "super_secret_bearer_token_12345"
        client = self._make_client(token=secret_token)
        mock_resp = _make_response(
            401,
            {"title": "Unauthorized", "detail": "Invalid token"},
        )

        with patch.object(client.session, "request", return_value=mock_resp):
            try:
                client.search_tweets("test")
            except APIError as e:
                error_msg = str(e)
                self.assertNotIn(secret_token, error_msg)

    def test_token_not_in_rate_limit_error(self):
        """RateLimitError メッセージにトークンが含まれないこと"""
        secret_token = "super_secret_bearer_token_67890"
        client = self._make_client(token=secret_token)
        client.max_retries = 0

        mock_resp = _make_response(
            429,
            {"title": "Too Many Requests"},
            headers={"Retry-After": "60"},
        )

        with patch.object(client.session, "request", return_value=mock_resp):
            with patch("time.sleep"):
                try:
                    client.search_tweets("test")
                except RateLimitError as e:
                    self.assertNotIn(secret_token, str(e))

    # ------------------------------------------------------------------
    # Authorization header 確認
    # ------------------------------------------------------------------
    def test_bearer_token_in_auth_header(self):
        """Bearer Token が Authorization ヘッダーに正しく設定されること"""
        token = "my_test_bearer_token"
        client = XClient(bearer_token=token)
        auth_header = client.session.headers.get("Authorization", "")
        self.assertEqual(auth_header, f"Bearer {token}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
