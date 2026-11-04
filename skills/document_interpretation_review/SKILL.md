---
name: document_interpretation_review
description: "Interpret a contract, financial-product or legal document's operative terms and cross-check with a second agent before reporting a conclusion, whenever the interpretation drives a signing, payment or commitment decision."
---

# Document Interpretation Review

Born 2026-11-04 from two failures in the a fund agreement review (ledger signatures `contract-clause-misread-definitive` and `high-stakes-interpretation-without-second-review`): a definitive "annual 7.5%" reading of a distribution cap that the text states per calculation period (quarterly, ≈30%/yr), delivered solo without an independent review, two days before a ¥50M signing. the operator's own reading was the textually natural one.

## When this applies

Before reporting a conclusion about what an operative clause of a contract, fund document, or other legal/financial document means, when that meaning drives a decision the operator will act on — signing, paying, committing, cancelling. As a guide: any commitment of ¥10M or more, and any signing regardless of amount.

## Procedure

1. **Read the clause with its machinery, not as a fragment.**
   - Read the operative clause together with its defined terms (period definitions such as 計算期間/計算期日， party definitions) and its cross-references to other articles.
   - Check how the *same document* expresses the same kind of quantity elsewhere. If the document marks annual rates expressly where it means them (e.g. 「年36パーセント」「年14.0%」）, the absence of that marker in the clause under review is evidence, not noise.
   - Never anchor a reading on a single formula fragment (a /365 day-count, a percentage, a defined term) without the period structure it operates in.

2. **Independent second-agent review before delivery.**
   - Have a different model (Opus or Codex, per the VM's working invocations) read the extracted full text and answer the interpretation questions independently, before the conclusion goes to the operator.
   - Reconcile disagreements explicitly. If a genuine ambiguity survives both readings, report both readings with their amounts — never collapse to a single confident number.
   - The loan-draft dual review (primary + Codex check) is the model; this skill makes it the default for interpretations too, not only for drafts.

3. **Report confidence as the text supports it.**
   - Distinguish "the text says X" from "X is the natural reading; the counter-reading is Y, and here is what turns on it".
   - A first-pass reading that a check later overturns is corrected openly, in the same reply that delivers the check result.

4. **On a correction, close the loop the same session.**
   - Record the failure in the failure ledger (`failure_ledger.py add`) in the session where it happens, per the `failure_mechanisms` skill.
