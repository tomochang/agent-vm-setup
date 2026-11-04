---
name: grok-search
description: Real-time search over X/Twitter and the web via the Grok API (x_search + web_search).
---

# grok-search — Grok API リアルタイム検索スキル

## 概要

xAI の Grok API (`https://api.x.ai/v1/responses`) を使って、X/Twitter のポスト・トレンドと一般 Web を同時または個別にリアルタイム検索するスキル。

---

## セットアップ

```bash
# 必須: xAI API キーを環境変数に設定
export XAI_API_KEY="xai-..."
```

`requests` がインストールされていない場合は `urllib` にフォールバックします。

---

## CLI

```bash
# X/Twitter 検索
python3 skills/grok-search/scripts/grok_search.py x "AI news today"
python3 skills/grok-search/scripts/grok_search.py x "NVDA earnings" --domain-filter x.com

# Web 検索
python3 skills/grok-search/scripts/grok_search.py web "latest Claude Code updates"

# 統合検索（X + Web 同時）
python3 skills/grok-search/scripts/grok_search.py both "investment signals semiconductor"

# JSON 出力（引用・コスト情報含む）
python3 skills/grok-search/scripts/grok_search.py x "AI news" --json
```

### JSON 出力形式

```json
{
  "text": "Result text...",
  "citations": [
    {
      "url": "https://x.com/user/status/123",
      "title": "Post title",
      "start": 0,
      "end": 42
    }
  ],
  "tool_calls": [
    {"name": "x_semantic_search", "query": "AI news"}
  ],
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "cost_usd": 0.15
  }
}
```

---

## Python API

```python
from skills.grok_search.scripts.grok_search import GrokSearch

# 環境変数 XAI_API_KEY を自動読み込み
client = GrokSearch()

# 明示的にキーを渡す場合
client = GrokSearch(api_key="xai-...")

# X/Twitter 検索
result = client.search_x("AI news today")

# Web 検索
result = client.search_web("Claude Code updates")

# 統合検索
result = client.search_both("investment signals")

# ドメインフィルタ付き
result = client.search_x("NVDA earnings", domain_filter="x.com")

# 結果フィールド
print(result.text)           # テキスト回答
print(result.citations)      # [{url, title, start, end}]
print(result.usage)          # {prompt_tokens, completion_tokens, cost_usd}
print(result.tool_calls)     # [{name, query}]
```

---

## エラーハンドリング

```python
from grok_search import GrokSearch, GrokSearchError, GrokSearchRateLimitError, GrokSearchTimeoutError

try:
    result = client.search_x("test")
except GrokSearchRateLimitError:
    print("レート制限 — しばらく待ってから再試行")
except GrokSearchTimeoutError:
    print("タイムアウト（デフォルト60秒）")
except GrokSearchError as e:
    print(f"エラー: {e}")
```

---

## API 仕様

| 項目 | 値 |
|------|----|
| エンドポイント | `https://api.x.ai/v1/responses` |
| モデル | `grok-4-1-fast-non-reasoning`（コスト最適） |
| 認証 | Bearer Token（`XAI_API_KEY`） |
| タイムアウト | 60秒（デフォルト） |
| コスト単位 | `cost_in_usd_ticks`（1 tick = 1e-6 USD） |

---

## ⚠️ セキュリティ注意事項

1. **APIキーの秘匿**: `XAI_API_KEY` はコード・ログ・エラーメッセージに絶対に含めないこと。本スクリプトはエラー出力にキーが漏れないよう設計されています。

2. **個人情報**: X/Twitter の検索結果にはユーザーの個人情報（氏名、ハンドル名、位置情報等）が含まれる場合があります。取得したデータを外部サービスに転送・保存する際は適切な配慮を行うこと。

3. **レート制限**: xAI API のレート制限に注意。`GrokSearchRateLimitError` (HTTP 429) が発生した場合は指数バックオフ後に再試行してください。

4. **コスト管理**: `result.usage["cost_usd"]` で毎回のコストを確認し、意図しない大量消費を防ぐこと。

---

## テスト実行

```bash
cd /workspace/skills/grok-search
python3 -m pytest scripts/test_grok_search.py -v
# 24 tests, 全パス（mockedテスト、実APIキー不要）
```

---

## ファイル構成

```
skills/grok-search/
├── SKILL.md                 # このファイル
└── scripts/
    ├── grok_search.py       # メインクライアント + CLI
    └── test_grok_search.py  # 24テストケース（TDD）
```
