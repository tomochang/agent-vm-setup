---
name: x-scraper
description: Use the X/Twitter API v2 directly for tweet search, user lookup, and trend retrieval, with no external SaaS dependency.
---

# x-scraper — X/Twitter API スクレイパースキル

X/Twitter API v2 を直接叩いて、ツイート検索・ユーザー情報取得・トレンド取得を行うスキル。
外部SaaS（Xquik等）に依存しない。

---

## セットアップ

### 1. 依存インストール

```bash
cd /workspace/skills/x-scraper
bash scripts/install.sh
```

または直接:

```bash
pip install requests
```

### 2. Bearer Token 取得

1. [X Developer Portal](https://developer.twitter.com/en/portal/dashboard) にアクセス
2. プロジェクト・アプリを作成（Free tierでも検索APIは利用可）
3. 「Keys and tokens」→「Bearer Token」を生成
4. 環境変数に設定:

```bash
export X_BEARER_TOKEN='your_bearer_token_here'
```

---

## CLI 使い方

### ツイート検索

```bash
python3 scripts/x_client.py search "keyword" --max 10
python3 scripts/x_client.py search "#AI" --max 20 --json
python3 scripts/x_client.py search "from:elonmusk" --max 5
```

### ユーザー情報取得

```bash
python3 scripts/x_client.py user "elonmusk"
python3 scripts/x_client.py user "openai" --json
```

### トレンド取得

```bash
# グローバルトレンド
python3 scripts/x_client.py trends

# 日本のトレンド (WOEID: 23424856)
python3 scripts/x_client.py trends --woeid 23424856

# 主要WOEID
#   1        = Global
#   23424856 = Japan
#   23424977 = United States
#   23424975 = United Kingdom
```

### ツイート詳細取得

```bash
python3 scripts/x_client.py tweet "1234567890123456789"
python3 scripts/x_client.py tweet "1234567890123456789" --json
```

---

## ライブラリとして使う

```python
from scripts.x_client import XClient

client = XClient(bearer_token="your_token")

# ツイート検索
result = client.search_tweets("Python", max_results=10)
for tweet in result["data"]:
    print(tweet["text"])

# ユーザー情報
user_data = client.get_user("elonmusk")
print(user_data["data"]["public_metrics"]["followers_count"])

# トレンド
trends = client.get_trends(woeid=23424856)
for t in trends[0]["trends"][:10]:
    print(t["name"])

# ツイート詳細
tweet = client.get_tweet("1234567890123456789")
print(tweet["data"]["public_metrics"])
```

---

## エラーハンドリング

```python
from scripts.x_client import XClient, MissingTokenError, RateLimitError, APIError

try:
    client = XClient()
    result = client.search_tweets("test")
except MissingTokenError as e:
    print(f"トークン未設定: {e}")
except RateLimitError as e:
    print(f"レート制限: {e}")
except APIError as e:
    print(f"APIエラー {e.status_code}: {e}")
```

---

## テスト実行

```bash
cd /workspace/skills/x-scraper
python3 -m pytest scripts/test_x_client.py -v
```

---

## 技術仕様

| 項目 | 内容 |
|------|------|
| API | X API v2 (tweets/search/recent, users/by/username, tweets/:id) + v1.1 (trends) |
| 認証 | Bearer Token (App-only auth) |
| 依存 | Python 3.10+ / requests |
| レート制限 | 429レスポンス時、Retry-Afterヘッダーに従い自動待機・リトライ |
| タイムアウト | 30秒 |

### X API v2 Free Tier 制限 (2024年時点)

| エンドポイント | 制限 |
|----------------|------|
| tweets/search/recent | 1リクエスト/15分 (Free), 180/15分 (Basic以上) |
| users/by/username | 500/15分 |
| tweets/:id | 15/15分 (Free) |

> Free tierはきつい制限があります。本格利用にはBasic($100/月)以上を推奨。

---

## ⚠️ セキュリティ・プライバシー注意事項

### Bearer Token の管理

- **Bearer TokenはGitにコミットしない。** `.gitignore` に `.env` を追加
- ログ・エラーメッセージにTokenが出力されないよう実装済み
- `shell=True` は使用していない

### 取得データの個人情報

X APIのレスポンスには以下の個人情報が含まれる場合があります：

- **ユーザーID、ユーザー名、表示名**
- **プロフィール文、プロフィール画像URL**
- **フォロワー数・フォロー数などの統計情報**
- **ツイート本文（位置情報が含まれる場合も）**

取得・保存・利用時は以下に注意：

1. **X Terms of Service に従うこと**
   → https://developer.twitter.com/en/developer-terms/agreement-and-policy
2. **個人を特定できる情報の不要な保存を避ける**
3. **スクレイピング結果の第三者への無断提供・販売禁止**
4. **削除済みツイートのキャッシュを持ち続けないこと**

---

## ファイル構成

```
skills/x-scraper/
├── SKILL.md              # このファイル
└── scripts/
    ├── x_client.py       # メインクライアント
    ├── test_x_client.py  # pytest テストスイート
    └── install.sh        # 依存インストールスクリプト
```
