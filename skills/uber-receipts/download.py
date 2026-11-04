#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "playwright",
# ]
# ///
"""
Uber領収書ダウンロード＆決済手段別分類

Usage:
    uv run download.py --days 30              # 直近30日分
    uv run download.py --month 2026/1         # 2026年1月分
    uv run download.py --start 2026-01-01 --end 2026-01-31
    uv run download.py --all                  # 全件

前提条件:
    1. Chrome/Chromiumをリモートデバッグモードで起動:
       /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
    2. ブラウザでUber (riders.uber.com) にログイン済み

Based on: https://til.danny.spesh.com/tils/uber-receipt-downloader
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright, Page, Browser

# receipt_lib を skills/ からインポート
sys.path.insert(0, str(Path(__file__).parent.parent))

from receipt_lib.classifier import classify_by_text


def classify_payment_method(text: str) -> str:
    """PDFまたはページコンテンツから決済手段を判定 (receipt_lib に委譲)"""
    return classify_by_text(text).value


# ============================================================
# ブラウザ操作
# ============================================================

def connect_to_browser(cdp_url: str = "http://localhost:9222") -> tuple[Browser, Page]:
    """既存のChromeセッションに接続"""
    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp(cdp_url)

    # 既存のコンテキストを使用（ログイン状態を維持）
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    page = context.pages[0] if context.pages else context.new_page()

    return browser, page


def fetch_trip_ids(page: Page, start_date: datetime | None, end_date: datetime | None) -> list[dict]:
    """トリップ一覧を取得"""
    trips = []
    page.goto("https://riders.uber.com/trips", wait_until="networkidle")
    time.sleep(2)

    while True:
        # トリップカードを取得
        trip_cards = page.query_selector_all('[data-testid="trip-card"]')
        if not trip_cards:
            # 別のセレクタを試す
            trip_cards = page.query_selector_all('a[href*="/trips/"]')

        for card in trip_cards:
            href = card.get_attribute('href') or ''
            trip_id_match = re.search(r'/trips/([a-f0-9-]+)', href)
            if not trip_id_match:
                continue

            trip_id = trip_id_match.group(1)

            # 日付を取得（カード内のテキストから）
            text = card.inner_text()
            date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4}|\w+ \d{1,2}, \d{4})', text)
            trip_date = None
            if date_match:
                try:
                    date_str = date_match.group(1)
                    # フォーマットを判定して解析
                    for fmt in ['%m/%d/%y', '%m/%d/%Y', '%B %d, %Y', '%b %d, %Y']:
                        try:
                            trip_date = datetime.strptime(date_str, fmt)
                            break
                        except ValueError:
                            continue
                except Exception:
                    pass

            # 日付フィルタ
            if trip_date:
                if start_date and trip_date < start_date:
                    continue
                if end_date and trip_date > end_date:
                    continue

            trips.append({
                'id': trip_id,
                'date': trip_date,
                'text': text[:100],
            })

        # 「もっと見る」ボタンをクリック
        more_button = page.query_selector('button:has-text("More"), button:has-text("もっと見る")')
        if more_button and more_button.is_visible():
            more_button.click()
            time.sleep(2)
        else:
            break

    # 重複除去
    seen = set()
    unique_trips = []
    for t in trips:
        if t['id'] not in seen:
            seen.add(t['id'])
            unique_trips.append(t)

    return unique_trips


def download_receipt(page: Page, trip_id: str, output_dir: Path) -> dict | None:
    """個別のトリップ詳細ページから領収書をダウンロード"""
    url = f"https://riders.uber.com/trips/{trip_id}"
    page.goto(url, wait_until="networkidle")
    time.sleep(1)

    # ページコンテンツを取得
    content = page.content()
    text = page.inner_text('body')

    # 日付を抽出
    date_match = re.search(r'(\d{4}-\d{2}-\d{2}|\w+ \d{1,2}, \d{4})', text)
    trip_date = datetime.now().strftime('%Y-%m-%d')
    if date_match:
        try:
            for fmt in ['%Y-%m-%d', '%B %d, %Y', '%b %d, %Y']:
                try:
                    trip_date = datetime.strptime(date_match.group(1), fmt).strftime('%Y-%m-%d')
                    break
                except ValueError:
                    continue
        except Exception:
            pass

    # 金額を抽出
    amount_match = re.search(r'[¥$][\d,]+(?:\.\d{2})?', text)
    amount = amount_match.group(0) if amount_match else 'unknown'
    amount_clean = re.sub(r'[¥$,]', '', amount)

    # 決済手段を判定
    payment_method = classify_payment_method(text)

    # 領収書ボタンをクリック
    receipt_button = page.query_selector('button:has-text("Receipt"), button:has-text("領収書"), a:has-text("Receipt")')
    if not receipt_button:
        print(f"  Warning: Receipt button not found for {trip_id}")
        return None

    receipt_button.click()
    time.sleep(2)

    # PDFダウンロードボタンを探す
    with page.expect_download(timeout=30000) as download_info:
        pdf_button = page.query_selector('button:has-text("Download PDF"), button:has-text("PDF"), a[href*=".pdf"]')
        if pdf_button:
            pdf_button.click()
        else:
            # 印刷ダイアログからPDF保存を試みる
            page.keyboard.press('Control+P')
            time.sleep(1)
            return None

    download = download_info.value

    # ファイル名を生成: YYYY-MM-DD_金額_決済手段_tripid.pdf
    safe_method = payment_method.replace('/', '-')
    filename = f"{trip_date}_{amount_clean}JPY_{safe_method}_{trip_id[:8]}.pdf"
    filepath = output_dir / filename

    download.save_as(filepath)

    return {
        'trip_id': trip_id,
        'date': trip_date,
        'amount': amount,
        'payment_method': payment_method,
        'filename': filename,
        'filepath': str(filepath),
    }


def process_trips(page: Page, trips: list[dict], output_dir: Path) -> list[dict]:
    """複数のトリップを処理"""
    results = []
    total = len(trips)

    for i, trip in enumerate(trips, 1):
        trip_id = trip['id']
        print(f"[{i}/{total}] Processing trip {trip_id}...")

        try:
            result = download_receipt(page, trip_id, output_dir)
            if result:
                results.append(result)
                print(f"  ✓ {result['date']} {result['amount']} ({result['payment_method']})")
            else:
                print(f"  ✗ Failed to download")
        except Exception as e:
            print(f"  ✗ Error: {e}")

        time.sleep(1)  # レート制限回避

    return results


def generate_summary(results: list[dict], output_dir: Path) -> str:
    """決済手段別のサマリーを生成 (receipt_lib を活用)"""
    from receipt_lib.models import Receipt, ReceiptSource, PaymentMethod
    from receipt_lib.output import (
        generate_summary as _generate_summary,
        save_results_json,
    )

    # dict → Receipt 変換
    receipts = []
    for r in results:
        # PaymentMethod enum を逆引き
        pm = PaymentMethod.OTHER
        for member in PaymentMethod:
            if member.value == r['payment_method']:
                pm = member
                break

        try:
            dt = datetime.strptime(r['date'], '%Y-%m-%d')
        except (ValueError, TypeError):
            dt = datetime.now()

        amount_str = re.sub(r'[^\d]', '', r.get('amount', '0'))
        amount = int(amount_str) if amount_str else 0

        receipts.append(Receipt(
            source=ReceiptSource.UBER,
            date=dt,
            amount=amount,
            payment_method=pm,
            filename=r['filename'],
            filepath=r.get('filepath', ''),
        ))

    # summary.md
    summary_path = output_dir / "summary.md"
    summary = _generate_summary(receipts, output_path=summary_path, title="Uber領収書 分類結果")

    # results.json (既存フォーマット互換のため元のdictも保存)
    json_path = output_dir / "results.json"
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))

    return summary


# ============================================================
# メイン
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Uber領収書ダウンロード＆決済手段別分類")
    parser.add_argument('--days', type=int, help='直近N日分')
    parser.add_argument('--month', help='対象月 (YYYY/M または YYYY-MM)')
    parser.add_argument('--start', help='開始日 (YYYY-MM-DD)')
    parser.add_argument('--end', help='終了日 (YYYY-MM-DD)')
    parser.add_argument('--all', action='store_true', help='全件取得')
    parser.add_argument('--output', '-o', default='./receipts', help='出力ディレクトリ')
    parser.add_argument('--cdp-url', default='http://localhost:9222', help='Chrome DevTools Protocol URL')
    args = parser.parse_args()

    # 日付範囲を決定
    start_date = None
    end_date = None

    if args.days:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.days)
    elif args.month:
        # YYYY/M または YYYY-MM をパース
        match = re.match(r'(\d{4})[/-](\d{1,2})', args.month)
        if match:
            year, month = int(match.group(1)), int(match.group(2))
            start_date = datetime(year, month, 1)
            if month == 12:
                end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = datetime(year, month + 1, 1) - timedelta(days=1)
        else:
            print(f"Error: Invalid month format: {args.month}")
            sys.exit(1)
    elif args.start and args.end:
        start_date = datetime.strptime(args.start, '%Y-%m-%d')
        end_date = datetime.strptime(args.end, '%Y-%m-%d')
    elif args.all:
        pass  # フィルタなし
    else:
        parser.print_help()
        sys.exit(1)

    # 出力ディレクトリ
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("Uber領収書ダウンロード")
    print("=" * 50)
    if start_date:
        print(f"期間: {start_date.strftime('%Y-%m-%d')} 〜 {end_date.strftime('%Y-%m-%d')}")
    else:
        print("期間: 全件")
    print(f"出力: {output_dir.absolute()}")
    print()

    # ブラウザに接続
    print("Connecting to browser...")
    try:
        browser, page = connect_to_browser(args.cdp_url)
    except Exception as e:
        print(f"\nError: Could not connect to browser at {args.cdp_url}")
        print("Make sure Chrome is running with --remote-debugging-port=9222")
        print(f"\nStart Chrome with:")
        print('  /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222')
        sys.exit(1)

    print("Connected!")
    print()

    # トリップ一覧を取得
    print("Fetching trips...")
    trips = fetch_trip_ids(page, start_date, end_date)
    print(f"Found {len(trips)} trips")
    print()

    if not trips:
        print("No trips found in the specified date range.")
        return

    # 領収書をダウンロード
    print("Downloading receipts...")
    results = process_trips(page, trips, output_dir)
    print()

    # サマリー生成
    if results:
        summary = generate_summary(results, output_dir)
        print("=" * 50)
        print(summary)
        print("=" * 50)
        print(f"\nSaved to: {output_dir.absolute()}")
    else:
        print("No receipts downloaded.")


if __name__ == '__main__':
    main()
