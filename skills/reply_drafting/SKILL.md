---
name: reply_drafting
description: Draft replies and messages in the operator's own voice — read the operator's voice examples and the actual thread before drafting, match register to the relationship, never corporate-formal to friends. Use whenever drafting a reply, decline, thank-you, scheduling message or any text the operator will send.
---

# Reply drafting （返信スキル)

the operator's voice already exists as data. Never invent a tone from scratch — ground every draft in it.

## Sources to read BEFORE drafting (in this order)

1. **The actual thread** with that person/group (Beeper/Gmail full history) — the register the operator uses *there* wins over every generic rule below. Note his sentence length, です・ます/タメ口 level, emoji and ！ usage with this specific counterpart.
2. **His voice examples**: `the voice-examples checkout/data/voice/examples.md` (his ai-chief-of-staff repo, cloned on this VM; `gh repo clone operator/voice-examples` if missing). NG/OK pairs distilled from his real messages.
3. **records repo `SOUL.md`** audience sections （対・外部ビジネス／カジュアル／個人メッセージ） and `private/operator-preferences.md` communication rules: recipient's feelings first; initiative + confidence + kindness; connection before advice.

## His voice, distilled from the examples

- **Short.** One or two sentences often beat a paragraph. Cut filler openings.
- **React from his own axis**, not the therapist pattern (empathy + question). ❌「素敵だね！何飲んだの？」 → ✅「あ、ここ気になってた。今度行こ」
- **Register = relationship.** Close/friends: plain casual, zero keigo piles — excessive formality creates distance and reads wrong. ❌「ご都合いかがでしょうか？」to a friend → ✅「水木どっちか空いてます」
- **Land with his own move**: a proposal, a next step, a decision — not an open-ended question dumped back on the other person.
- **Meaning over titles/details** when describing people or situations: what they mean to the recipient, in one line.
- Business counterparts (firms, officials, first contacts): polite です・ます with numbered structure when listing points — modeled on past sent messages to professional firms (fictional example: a message to the invented firm 'Aoba Consulting'). Polite but not servile; he does not pile up apologies.
- Signature on business mail: 「the operator」.

## Failure that created this skill (2026-11-04)

Drafted a decline to a friend's friend-group party invite as 「11/8の上海蟹パーティー、今回は参加を見送らせてください」 — corporate register to friends. the operator: 「口調がダメだね。これスキルにしたいな。返信スキル。」
Correct shape for a friend decline: gratitude for the invite → plain regret → one-line reason → warm open door, in the thread's own register:
「誘ってくれてありがとうございます！11/8ですが、その週末は先約が入ってしまい、今回は参加できそうにありません。残念です。また誘ってください！」

## Names and facts in drafts

- **Copy proper nouns in the exact script of the source record.** ミライ stays ミライ (katakana) — never guess kanji for a name (the fictional example's wrong guess was 未来).
- Facts (dates, amounts, decisions) come from the record, verified before drafting — see skill `research_method` (decision-check) and `todo_verification` when a draft touches todo state.

## Presenting a draft — grounding citation is mandatory

A draft is never presented alone. Always attach one line of grounding:

**根拠： 相手の最終メッセージ（日時・要旨）／ the operator の最終送信（日時・文面）／ このスレッドでのレジスタ**

If you cannot fill that line in, you have not read the thread — stop and read it first. This rule exists because on 2026-11-04, minutes after this skill was created, two successive a friend drafts were still written without reading the thread (they ignored the operator's own 「調整中」 message and the fact it was sent 1:1, not to the group). A rule on paper does not fire by itself; the citation makes skipping visible at presentation time.

## Approval discipline (unchanged standing rules)

- Drafts for unimportant messages may be sent without prior approval (2026-11-01 override); important or personal messages go to the operator first.
- Confirm the scope by topic before sending a personal or group message — a general 「進めて」 for another topic is not approval for this one.
- After sending, verify by read-back in the thread, and mirror the send to the SoT in the same run.
