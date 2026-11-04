#!/usr/bin/env python3
"""
X/Twitter API v2 Client
=======================
Bearer Token認証でツイート検索・ユーザー情報取得・トレンド取得を行う。

Usage (CLI):
    python3 x_client.py search "keyword" --max 10 [--json]
    python3 x_client.py user "username" [--json]
    python3 x_client.py trends [--woeid 23424856] [--json]
    python3 x_client.py tweet "tweet_id" [--json]

Library usage:
    from x_client import XClient
    client = XClient(bearer_token="...")
    results = client.search_tweets("keyword", max_results=10)
"""

import os
import sys
import time
import json
import argparse
from typing import Optional

try:
    import requests
except ImportError:
    print("Error: 'requests' library is required. Run: pip install requests", file=sys.stderr)
    sys.exit(1)


class XClientError(Exception):
    """X API クライアントエラー基底クラス"""
    pass


class MissingTokenError(XClientError):
    """Bearer Token未設定エラー"""
    pass


class RateLimitError(XClientError):
    """レート制限エラー"""
    pass


class APIError(XClientError):
    """API エラー（4xx/5xx）"""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(message)


class XClient:
    """
    X/Twitter API v2 クライアント

    Args:
        bearer_token: X API Bearer Token。省略時は環境変数 X_BEARER_TOKEN を使用。
        max_retries: レート制限時の最大リトライ回数（デフォルト: 3）
    """

    BASE_URL = "https://api.twitter.com/2"
    # v1.1エンドポイント（トレンド取得用）
    BASE_URL_V1 = "https://api.twitter.com/1.1"

    def __init__(self, bearer_token: Optional[str] = None, max_retries: int = 3):
        token = bearer_token or os.environ.get("X_BEARER_TOKEN")
        if not token:
            raise MissingTokenError(
                "X_BEARER_TOKEN が設定されていません。\n"
                "取得手順:\n"
                "  1. https://developer.twitter.com/en/portal/dashboard にアクセス\n"
                "  2. プロジェクト・アプリを作成 (Free tierでも利用可)\n"
                "  3. 「Keys and tokens」→「Bearer Token」を生成\n"
                "  4. 環境変数に設定: export X_BEARER_TOKEN='your_token_here'"
            )
        self._token = token
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self._token}",
            "User-Agent": "x-scraper-skill/1.0",
        })

    def _request(self, method: str, url: str, **kwargs) -> dict:
        """
        HTTPリクエスト送信（レート制限リトライ付き）
        Bearer Tokenはログ・エラーメッセージに含めない。
        """
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.request(method, url, timeout=30, **kwargs)
            except requests.RequestException as e:
                raise XClientError(f"ネットワークエラー: {e}") from e

            if resp.status_code == 200:
                return resp.json()

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 60))
                if attempt < self.max_retries:
                    time.sleep(retry_after)
                    continue
                raise RateLimitError(
                    f"レート制限に達しました。{retry_after}秒後に再試行してください。"
                )

            # 4xx/5xx エラー（トークンはメッセージに含めない）
            try:
                error_body = resp.json()
                detail = error_body.get("detail") or error_body.get("title") or str(error_body)
            except Exception:
                detail = resp.text[:200]

            raise APIError(
                resp.status_code,
                f"API エラー {resp.status_code}: {detail}"
            )

        raise RateLimitError("最大リトライ回数を超えました。")

    def search_tweets(
        self,
        query: str,
        max_results: int = 10,
        tweet_fields: Optional[list] = None,
    ) -> dict:
        """
        ツイート検索 (recent search)

        Args:
            query: 検索クエリ（例: "keyword", "#hashtag", "from:user"）
            max_results: 最大取得件数 (10〜100)
            tweet_fields: 追加フィールド一覧

        Returns:
            API レスポンス dict（data, meta を含む）
        """
        max_results = max(10, min(100, max_results))
        fields = tweet_fields or ["created_at", "author_id", "public_metrics", "text"]
        params = {
            "query": query,
            "max_results": max_results,
            "tweet.fields": ",".join(fields),
        }
        url = f"{self.BASE_URL}/tweets/search/recent"
        return self._request("GET", url, params=params)

    def get_user(self, username: str, user_fields: Optional[list] = None) -> dict:
        """
        ユーザー情報取得

        Args:
            username: Xユーザー名（@なし）
            user_fields: 追加フィールド一覧

        Returns:
            API レスポンス dict（data フィールドにユーザー情報）
        """
        fields = user_fields or [
            "id", "name", "username", "description",
            "public_metrics", "created_at", "verified",
        ]
        params = {"user.fields": ",".join(fields)}
        url = f"{self.BASE_URL}/users/by/username/{username}"
        return self._request("GET", url, params=params)

    def get_trends(self, woeid: int = 1) -> dict:
        """
        トレンド取得 (v1.1 API)

        Args:
            woeid: Where On Earth ID (1=Global, 23424856=Japan)

        Returns:
            API レスポンス dict
        Note:
            トレンドAPIはv1.1のみ。Elevated以上のアクセスレベルが必要な場合あり。
        """
        url = f"{self.BASE_URL_V1}/trends/place.json"
        params = {"id": woeid}
        return self._request("GET", url, params=params)

    def get_tweet(self, tweet_id: str, tweet_fields: Optional[list] = None) -> dict:
        """
        ツイート詳細取得

        Args:
            tweet_id: ツイートID
            tweet_fields: 追加フィールド一覧

        Returns:
            API レスポンス dict（data フィールドにツイート情報）
        """
        fields = tweet_fields or [
            "created_at", "author_id", "public_metrics",
            "text", "entities", "lang",
        ]
        params = {"tweet.fields": ",".join(fields)}
        url = f"{self.BASE_URL}/tweets/{tweet_id}"
        return self._request("GET", url, params=params)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_result(data: dict, as_json: bool, formatter=None):
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif formatter:
        formatter(data)
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


def _format_tweets(data: dict):
    tweets = data.get("data", [])
    meta = data.get("meta", {})
    print(f"[{meta.get('result_count', len(tweets))}件のツイート]")
    for t in tweets:
        metrics = t.get("public_metrics", {})
        print(f"\nID: {t.get('id')}")
        print(f"  {t.get('text', '')[:140]}")
        print(f"  ❤️ {metrics.get('like_count',0)}  🔁 {metrics.get('retweet_count',0)}  💬 {metrics.get('reply_count',0)}")


def _format_user(data: dict):
    u = data.get("data", {})
    m = u.get("public_metrics", {})
    print(f"@{u.get('username')} ({u.get('name')})")
    print(f"  {u.get('description', '')[:100]}")
    print(f"  フォロワー: {m.get('followers_count',0)}  フォロー中: {m.get('following_count',0)}")
    print(f"  ツイート数: {m.get('tweet_count',0)}")


def _format_trends(data):
    if isinstance(data, list) and data:
        trends = data[0].get("trends", [])
        print(f"[{len(trends)}件のトレンド]")
        for i, t in enumerate(trends[:20], 1):
            volume = t.get("tweet_volume") or "-"
            print(f"  {i:2}. {t.get('name')}  ({volume} tweets)")
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


def _format_tweet(data: dict):
    t = data.get("data", {})
    m = t.get("public_metrics", {})
    print(f"ID: {t.get('id')}")
    print(f"  {t.get('text','')}")
    print(f"  作成: {t.get('created_at','')}")
    print(f"  ❤️ {m.get('like_count',0)}  🔁 {m.get('retweet_count',0)}  💬 {m.get('reply_count',0)}  👀 {m.get('impression_count',0)}")


def main():
    parser = argparse.ArgumentParser(
        description="X/Twitter API v2 クライアント",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--json", action="store_true", dest="as_json", help="JSON形式で出力")

    sub = parser.add_subparsers(dest="command", required=True)

    # search
    p_search = sub.add_parser("search", help="ツイート検索")
    p_search.add_argument("query", help='検索クエリ (例: "python", "#AI", "from:elonmusk")')
    p_search.add_argument("--max", type=int, default=10, help="最大取得件数 (10-100, デフォルト: 10)")

    # user
    p_user = sub.add_parser("user", help="ユーザー情報取得")
    p_user.add_argument("username", help="Xユーザー名 (@なし)")

    # trends
    p_trends = sub.add_parser("trends", help="トレンド取得")
    p_trends.add_argument("--woeid", type=int, default=1, help="WOEID (1=Global, 23424856=Japan)")

    # tweet
    p_tweet = sub.add_parser("tweet", help="ツイート詳細取得")
    p_tweet.add_argument("tweet_id", help="ツイートID")

    args = parser.parse_args()

    try:
        client = XClient()
    except MissingTokenError as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        if args.command == "search":
            data = client.search_tweets(args.query, max_results=args.max)
            _print_result(data, args.as_json, _format_tweets)

        elif args.command == "user":
            data = client.get_user(args.username)
            _print_result(data, args.as_json, _format_user)

        elif args.command == "trends":
            data = client.get_trends(woeid=args.woeid)
            _print_result(data, args.as_json, _format_trends)

        elif args.command == "tweet":
            data = client.get_tweet(args.tweet_id)
            _print_result(data, args.as_json, _format_tweet)

    except RateLimitError as e:
        print(f"レート制限: {e}", file=sys.stderr)
        sys.exit(2)
    except APIError as e:
        print(f"APIエラー ({e.status_code}): {e}", file=sys.stderr)
        sys.exit(3)
    except XClientError as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
