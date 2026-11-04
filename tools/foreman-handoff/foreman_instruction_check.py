#!/usr/bin/env python3
"""Foreman instruction conformance check (the resident agent's pre-send gate).

Validates a draft F: instruction (resident agent -> Foreman, factory chat) against the
required sections of ~/workspace/reference/foreman-instruction-template.md.
Exit 0 = conformant; exit 1 = missing sections (listed on stdout as JSON).

Rule (the operator, 2026-11-03, after the risk-enumeration omission recurred):
no F: instruction is sent unless this check passes on the exact text.
Born from two failures of the same kind (2026-11-02 21:41 and 2026-11-03
09:04): instructions sent without the template's risk-first section.

Usage:
  foreman_instruction_check.py <draft-file>
  cat draft.txt | foreman_instruction_check.py -
"""
import json
import re
import sys

# (section name, list of marker-pattern groups; a group passes if ANY pattern hits)
REQUIRED = [
    ("subject_and_purpose", [r"件名", r"目的"]),
    ("completion_definition", [r"完了の定義", r"完了条件"]),
    ("scope_do", [r"やること", r"スコープ"]),
    ("scope_dont", [r"やらないこと"]),
    ("risk_enumeration", [r"リスク表", r"リスク.*洗い出し", r"リスク.*列挙", r"独立にリスク"]),
    ("budget_hard_cap", [r"上限\s*[0-9]", r"上限.*ハード", r"hard cap"]),
    ("report_at_70pct", [r"70\s*%"]),
    ("stop_condition", [r"停止", r"止めて報告", r"停止して報告"]),
    ("measured_reporting", [r"実測"]),
    ("report_format", [r"報告フォーマット", r"報告形式"]),
    ("escalation_format", [r"推奨", r"A/B", r"Ａ/Ｂ"]),
]


def check(text: str) -> dict:
    missing = []
    for name, patterns in REQUIRED:
        if not any(re.search(p, text) for p in patterns):
            missing.append(name)
    return {"ok": not missing, "missing": missing}


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"ok": False, "error": "usage: foreman_instruction_check.py <file|->"}))
        return 2
    if sys.argv[1] == "-":
        text = sys.stdin.read()
    else:
        with open(sys.argv[1], encoding="utf-8") as fh:
            text = fh.read()
    verdict = check(text)
    print(json.dumps(verdict, ensure_ascii=False))
    return 0 if verdict["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
