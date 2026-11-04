#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
S.RIDE領収書ダウンロード＆決済手段別分類

Usage:
    uv run download.py --month 2026/1
    uv run download.py --month 2026/1 --statement ~/company-statement.csv
    uv run download.py --latest

前提条件:
    1. gog CLI がインストール済み
    2. Gmail API 認証設定済み
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# receipt_lib を skills/ からインポート
sys.path.insert(0, str(Path(__file__).parent.parent))

from receipt_lib.models import PaymentMethod, Receipt, ReceiptSource
from receipt_lib.classifier import classify_by_company_statement
from receipt_lib.output import generate_summary, organize_receipt, save_results_json

SRIDE_SENDER = "noreply-invoice@cs.sride.co.jp"
FILENAME_PATTERN = re.compile(
    r"(\d{8})_(\d{4})_receipt_JPY(\d+)_([A-Z0-9]+)_taxifare\.pdf"
)


def run_gog(*args: str) -> str:
    """gog CLI を実行して stdout を返す"""
    cmd = ["gog"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error running: {' '.join(cmd)}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result.stdout


def search_sride_emails(month: str | None = None, max_results: int = 20) -> list[dict]:
    """S.RIDE領収書メールを検索

    Args:
        month: YYYY/M or YYYY-MM 形式 (None=全件)
        max_results: 最大件数

    Returns:
        スレッド情報のリスト
    """
    query = f"from:{SRIDE_SENDER} subject:領収書"
    if month:
        match = re.match(r"(\d{4})[/-](\d{1,2})", month)
        if match:
            year, mon = int(match.group(1)), int(match.group(2))
            # S.RIDEは月次まとめメールなので、対象月を含むメールを検索
            # 件名に "(YYYY/MM/DD - YYYY/MM/DD)" が含まれる
            query += f" {year}/{mon:02d}"

    output = run_gog("gmail", "search", query, "--max", str(max_results), "--json")
    data = json.loads(output)
    return data.get("threads", []) or []


def get_email_attachments(thread_id: str) -> tuple[str, list[dict]]:
    """メールの添付ファイル情報を取得

    Returns:
        (message_id, attachments_list)
    """
    output = run_gog("gmail", "get", thread_id, "--json")
    data = json.loads(output)
    message_id = data.get("message", {}).get("id", thread_id)
    attachments = data.get("attachments", [])
    return message_id, attachments


def download_attachment(
    message_id: str,
    attachment_id: str,
    output_dir: Path,
    filename: str,
) -> Path:
    """添付ファイルをダウンロード"""
    output_path = output_dir / filename
    run_gog(
        "gmail", "attachment",
        message_id, attachment_id,
        "--out", str(output_path),
    )
    return output_path


def parse_filename(filename: str) -> dict | None:
    """S.RIDEレシートのファイル名からメタデータを抽出

    Format: YYYYMMDD_HHMM_receipt_JPY{amount}_T{registration}_taxifare.pdf

    Returns:
        {"date": datetime, "amount": int, "registration": str} or None
    """
    m = FILENAME_PATTERN.match(filename)
    if not m:
        return None

    date_str, time_str, amount_str, registration = m.groups()
    try:
        dt = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M")
    except ValueError:
        return None

    return {
        "date": dt,
        "amount": int(amount_str),
        "registration": registration,
    }


def filter_attachments_by_month(
    attachments: list[dict],
    year: int,
    month: int,
) -> list[dict]:
    """指定月のレシートのみフィルタ"""
    filtered = []
    for att in attachments:
        meta = parse_filename(att["filename"])
        if meta and meta["date"].year == year and meta["date"].month == month:
            filtered.append(att)
    return filtered


def process_sride_receipts(
    month: str | None = None,
    statement_path: str | None = None,
    output_dir: Path | None = None,
    receipts_dir: Path | None = None,
) -> list[Receipt]:
    """S.RIDE領収書のメイン処理パイプライン"""
    if output_dir is None:
        output_dir = Path.home() / "records" / "receipts"
    if receipts_dir is None:
        receipts_dir = Path.home() / "records" / "receipts"

    # 月パース
    target_year, target_month = None, None
    if month:
        match = re.match(r"(\d{4})[/-](\d{1,2})", month)
        if match:
            target_year, target_month = int(match.group(1)), int(match.group(2))

    # 1. メール検索
    print("S.RIDE領収書メールを検索中...")
    threads = search_sride_emails(month=month)
    if not threads:
        print("S.RIDE領収書メールが見つかりません")
        return []

    print(f"  {len(threads)}件のメールスレッドが見つかりました")

    # 2. 添付ファイルをダウンロード
    receipts: list[Receipt] = []
    seen_filenames: set[str] = set()  # 重複排除用
    tmp_dir = output_dir / "tmp" / "sride"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    for thread in threads:
        thread_id = thread["id"]
        subject = thread.get("subject", "")
        print(f"\n  処理中: {subject}")

        message_id, attachments = get_email_attachments(thread_id)
        pdf_attachments = [a for a in attachments if a["filename"].endswith(".pdf")]

        # 月フィルタ
        if target_year and target_month:
            pdf_attachments = filter_attachments_by_month(
                pdf_attachments, target_year, target_month
            )

        print(f"  PDFファイル: {len(pdf_attachments)}件")

        for att in pdf_attachments:
            filename = att["filename"]
            attachment_id = att["attachmentId"]

            # 重複チェック
            if filename in seen_filenames:
                print(f"    - スキップ (重複): {filename}")
                continue
            seen_filenames.add(filename)

            # メタデータ抽出
            meta = parse_filename(filename)
            if not meta:
                print(f"    ✗ ファイル名解析失敗: {filename}")
                continue

            # ダウンロード
            filepath = download_attachment(message_id, attachment_id, tmp_dir, filename)
            print(f"    ✓ DL: {filename} (¥{meta['amount']:,})")

            # Receipt オブジェクト作成
            receipt = Receipt(
                source=ReceiptSource.SRIDE,
                date=meta["date"],
                amount=meta["amount"],
                payment_method=PaymentMethod.CREDIT_CARD,
                filename=filename,
                filepath=str(filepath),
                metadata={"registration": meta["registration"]},
            )

            # 3. 分類 (COMPANY_CARD突合)
            if statement_path:
                receipt.payment_method = classify_by_company_statement(
                    receipt, statement_path
                )

            receipts.append(receipt)

    if not receipts:
        print("\n対象のレシートが見つかりません")
        return []

    # 4. ファイル配置
    print(f"\n{len(receipts)}件のレシートを分類・配置中...")
    for receipt in receipts:
        dest = organize_receipt(receipt, receipts_dir=receipts_dir, copy=True)
        print(f"  → {dest.relative_to(receipts_dir)}")

    # 5. サマリー生成
    summary_path = receipts_dir / "sride_summary.md"
    summary = generate_summary(receipts, output_path=summary_path)

    # 6. results.json
    json_path = receipts_dir / "sride_results.json"
    save_results_json(receipts, json_path)

    # tmp クリーンアップ
    for f in tmp_dir.iterdir():
        f.unlink()
    tmp_dir.rmdir()

    return receipts


def main():
    parser = argparse.ArgumentParser(description="S.RIDE領収書ダウンロード＆分類")
    parser.add_argument("--month", help="対象月 (YYYY/M または YYYY-MM)")
    parser.add_argument("--latest", action="store_true", help="最新のメールのみ処理")
    parser.add_argument("--statement", help="COMPANY_CARD明細ファイルパス (CSV/JSON)")
    parser.add_argument("--output", "-o", default=None, help="出力ディレクトリ")
    args = parser.parse_args()

    if not args.month and not args.latest:
        parser.print_help()
        sys.exit(1)

    output_dir = Path(args.output) if args.output else None

    print("=" * 50)
    print("S.RIDE領収書ダウンロード")
    print("=" * 50)
    if args.month:
        print(f"対象月: {args.month}")
    if args.statement:
        print(f"COMPANY_CARD明細: {args.statement}")
    print()

    receipts = process_sride_receipts(
        month=args.month,
        statement_path=args.statement,
        output_dir=output_dir,
        receipts_dir=output_dir,
    )

    if receipts:
        print()
        print("=" * 50)
        company_count = sum(1 for r in receipts if r.payment_method == PaymentMethod.COMPANY_CARD)
        other_count = len(receipts) - company_count
        total_amount = sum(r.amount for r in receipts)
        print(f"処理完了: {len(receipts)}件 (COMPANY_CARD: {company_count}, その他: {other_count})")
        print(f"合計金額: ¥{total_amount:,}")
        print("=" * 50)


if __name__ == "__main__":
    main()
