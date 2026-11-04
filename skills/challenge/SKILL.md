---
name: challenge
description: "前提を壊す自律思考ループ。/challenge <トピック> or /challenge 3 <トピック> で発動"
user-invocable: true
---

# /challenge — 自律思考エンジン

前提を壊しに行く再帰的思考ループ。

## 発動

### ユーザーが `/challenge` と入力した場合
1. トピックを特定（`/challenge <トピック>` or 直前の会話から推測）
2. ラウンド数を特定（`/challenge 3 <トピック>` or デフォルト5）
3. サブエージェントをspawnして実行

### エージェントが自動提案する場合
以下を検出したら提案:
- 不可逆性が高い（M&A、大型ポジション、公開発信、契約）
- 前提が1つしかない仮説に依存
- 複数選択肢が拮抗
- 過去に同パターンで失敗した記録

提案文: 「これ、/challenge回した方がいいと思います。前提を壊してから進めますか？」

## 実行手順

### Step 1: 出力ディレクトリ作成
```bash
CHALLENGE_DIR="output/challenge/$(date -u +%Y%m%d-%H%M%S)"
mkdir -p "$CHALLENGE_DIR"
```

### Step 2: プロンプト構築
`scripts/challenge/challenge_prompt.md` を読み、`{output_dir}` を実際のパスに置換。

トピックのコンテキストを付加:
- 直近の会話履歴（関連部分）
- 関連ファイルがあればその内容
- ポートフォリオや意思決定の現状

### Step 3: サブエージェントspawn
```
sessions_spawn:
  task: [構築したプロンプト]
  mode: run
  label: "challenge-[トピック要約]"
```

### Step 4: 完了後の報告
サブエージェント完了後、`{output_dir}/synthesis.md` を読んで要約を報告:

```
🔴 /challenge 完了（N rounds）

■ 前提 → 変数化: X件
■ 崩壊した前提: Y件
■ メタ昇格: [上位の問い]

結論: [修正後の結論 or 「元の結論を支持」]
最大の発見: [最も重要な気づき]
```

詳細は `{output_dir}/` を参照と案内。

## ファイル構成
```
scripts/challenge/
  ENGINE.md              — 設計ドキュメント
  challenge_prompt.md    — サブエージェント用プロンプトテンプレート
skills/challenge/
  SKILL.md               — このファイル（メインエージェント用スキル）
output/challenge/
  YYYYMMDD-HHMMSS/       — 実行ごとの出力
    round-1.md
    round-2.md
    ...
    synthesis.md
    constants-to-variables.json
```
