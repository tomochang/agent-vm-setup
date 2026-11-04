---
name: schedule-reply
description: 日程調整の返信を作成・送信・後続処理まで一気通貫で実行する
---

# 日程調整返信ワークフロー

日程調整の返信を作成・送信・後続処理まで一気通貫で実行する。

**メッセージ本文:** $ARGUMENTS

## 食事・デートの返信は先に分岐

食事に誘う／店を選ぶ文脈では、`docs/agent-rules/workflows.md` の「レストラン予約アシスタント」と「食事の誘い・返信案の完了条件」を先に読む。本人の最新指定・過去の希望を候補と文面へ反映し、具体店の提案と検証済みURLを先に用意してから必要な時刻を詰める。勤務終了の連絡待ちだけの案や、業務MTG用の候補数・署名・時間帯を機械的に流用しない。選択済みの1店を再び3案へ広げない。食事の処理・送信後同期は同workflowで完結し、以下の業務日程用Phase 1〜3は適用しない。送信・予約・Calendar writeは承認と実行前関門に従う。

---

## Phase 1: 情報収集（返信案の前に必ず実行。スキップ厳禁）

**カレンダーを確認せずに返信案を作ることは絶対に禁止。**

1. **相手情報を取得**: `private/operator-relationships.md` からメッセージの送信者を検索し、関係性・属性を確認する
2. **空き時間を自動抽出**: 以下のコマンドを実行する

   ```bash
   node the records checkout/scripts/calendar-suggest.js --days 14 --prefer-start 11
   ```

   - 銀行系の相手の場合は `--bank` フラグを追加
   - `--prefer-start 11` は午前NGの好みを反映（`private/operator-preferences.md` 参照）

3. **好みを適用**: `private/operator-preferences.md` を読み、候補数（3〜5個）・署名（the operator）等を確認

---

## Phase 2: 返信案作成

- calendar-suggest.js の出力をフォーマットして返信案を生成する
- `SOUL.md` のトーンを反映する
- `IDENTITY.md` の人格設定を反映する
- 署名は「the operator」（`private/operator-preferences.md` 参照）

返信案をユーザーに提示し、承認を得てから送信する。

---

## Phase 3: 送信後処理（全自動・途中で止めない）

メール送信完了後、以下を**確認を挟まず全自動で**実行する：

1. **[仮]カレンダー登録**: 候補日すべてを `[仮]` でカレンダー登録

   ```bash
   gog calendar create operator-secondary@example.com \
     --summary "[仮] 〇〇さんとMTG" \
     --from "YYYY-MM-DDTHH:MM:00+09:00" \
     --to "YYYY-MM-DDTHH:MM:00+09:00"
   ```

   - `--account operator-secondary@example.com` は `gog calendar create` の第1引数として渡す
   - 候補日の数だけ繰り返す

2. **operator_relationships.md 更新**: 該当人物のセクションにやり取り履歴を追記（サービス事務連絡はスキップ可）

3. **todo.md 更新**: 予定テーブル + アクション待ちテーブルに反映

4. **commit & push**:
   ```bash
   cd the records checkout && git add -A && git commit -m "日程調整: 〇〇さんへの返信 + [仮]カレンダー登録" && python3 scripts/records_gate.py push
   ```

**Phase 3の4ステップがすべて完了するまでタスク完了にしない。**
