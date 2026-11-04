"""分類サービス

2つの分類モード:
1. テキストベース: PDF/ページにカード名が表示されるソース向け (Uber等)
2. COMPANY_CARD突合: 「クレジットカード利用」としか出ないソース向け (S.RIDE等)
   日付±1日 + 金額完全一致でマッチング
"""

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

from .models import PaymentMethod, Receipt

# テキストベース分類のパターン (優先度順)
PAYMENT_PATTERNS: list[tuple[PaymentMethod, list[str]]] = [
    (PaymentMethod.COMPANY_CARD, ["company"]),
    (PaymentMethod.PAYPAY, ["paypay"]),
    (PaymentMethod.CASH, ["cash", "現金"]),
    (PaymentMethod.AMEX, ["amex", "american express"]),
    (PaymentMethod.VISA, ["visa"]),
    (PaymentMethod.MASTERCARD, ["mastercard"]),
]


def classify_by_text(text: str) -> PaymentMethod:
    """PDFまたはページコンテンツから決済手段を判定 (テキストベース)"""
    text_lower = text.lower()
    for method, patterns in PAYMENT_PATTERNS:
        if any(p in text_lower for p in patterns):
            return method
    return PaymentMethod.OTHER


def classify_by_company_statement(
    receipt: Receipt,
    statement_path: str | Path | None = None,
    date_tolerance_days: int = 1,
) -> PaymentMethod:
    """COMPANY_CARD明細との突合で分類

    S.RIDE等、PDFに「クレジットカード利用」としか表示されないソース向け。
    日付±tolerance日 + 金額完全一致でマッチング。

    Args:
        receipt: 分類対象のレシート
        statement_path: COMPANY_CARD明細ファイルのパス (CSV or JSON)
                        None の場合は CREDIT_CARD を返す
        date_tolerance_days: 日付の許容誤差 (デフォルト1日)

    Returns:
        COMPANY_CARD (マッチ) または CREDIT_CARD (マッチなし/明細なし)
    """
    if statement_path is None:
        return PaymentMethod.CREDIT_CARD

    statement_path = Path(statement_path)
    if not statement_path.exists():
        return PaymentMethod.CREDIT_CARD

    entries = _load_statement(statement_path)
    if not entries:
        return PaymentMethod.CREDIT_CARD

    receipt_date = receipt.date.date() if isinstance(receipt.date, datetime) else receipt.date
    date_min = receipt_date - timedelta(days=date_tolerance_days)
    date_max = receipt_date + timedelta(days=date_tolerance_days)

    for entry in entries:
        entry_date = entry.get("date")
        entry_amount = entry.get("amount")
        if entry_date is None or entry_amount is None:
            continue
        if date_min <= entry_date <= date_max and entry_amount == receipt.amount:
            return PaymentMethod.COMPANY_CARD

    return PaymentMethod.CREDIT_CARD


def _load_statement(path: Path) -> list[dict]:
    """COMPANY_CARD明細をロード (CSV/JSON対応)"""
    entries = []

    if path.suffix == ".json":
        with open(path) as f:
            data = json.load(f)
        items = data if isinstance(data, list) else data.get("transactions", [])
        for item in items:
            date_str = item.get("date", item.get("transaction_date", ""))
            amount = item.get("amount", 0)
            try:
                date = _parse_date(date_str)
                entries.append({"date": date, "amount": abs(int(amount))})
            except (ValueError, TypeError):
                continue

    elif path.suffix == ".csv":
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                date_str = (
                    row.get("date")
                    or row.get("利用日")
                    or row.get("取引日")
                    or ""
                )
                amount_str = (
                    row.get("amount")
                    or row.get("金額")
                    or row.get("利用金額")
                    or "0"
                )
                try:
                    date = _parse_date(date_str)
                    amount = abs(int(amount_str.replace(",", "").replace("¥", "")))
                    entries.append({"date": date, "amount": amount})
                except (ValueError, TypeError):
                    continue

    return entries


def _parse_date(s: str) -> "datetime.date":
    """複数の日付フォーマットを試みてパース"""
    from datetime import date as date_type

    if isinstance(s, date_type):
        return s

    s = s.strip()
    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"]:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {s}")
