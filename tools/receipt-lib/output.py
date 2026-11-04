"""出力サービス - ファイル整理 + summary.md + results.json 生成"""

import json
import shutil
from datetime import datetime
from pathlib import Path

from .models import PaymentMethod, Receipt, ReceiptSource

# デフォルトのレシート格納先
DEFAULT_RECEIPTS_DIR = Path.home() / "clawd" / "receipts"


def organize_receipt(
    receipt: Receipt,
    receipts_dir: Path | None = None,
    copy: bool = True,
) -> Path:
    """レシートを分類ディレクトリに配置

    構造: {receipts_dir}/{company|other}/YYYYMM/{source}/{filename}

    Args:
        receipt: 配置対象のレシート
        receipts_dir: ベースディレクトリ (デフォルト: ~/clawd/receipts)
        copy: True=コピー, False=移動

    Returns:
        配置先のパス
    """
    if receipts_dir is None:
        receipts_dir = DEFAULT_RECEIPTS_DIR

    # COMPANY_CARD分類
    if receipt.payment_method == PaymentMethod.COMPANY_CARD:
        category = "company"
    else:
        category = "other"

    # YYYYMM
    month_str = receipt.date.strftime("%Y%m")

    # ソース名
    source_name = receipt.source.value

    dest_dir = receipts_dir / category / month_str / source_name
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_path = dest_dir / receipt.filename
    src_path = Path(receipt.filepath)

    if src_path.exists() and src_path != dest_path:
        if copy:
            shutil.copy2(src_path, dest_path)
        else:
            shutil.move(str(src_path), str(dest_path))

    # レシートのfilepathを更新
    receipt.filepath = str(dest_path)

    return dest_path


def generate_summary(
    receipts: list[Receipt],
    output_path: Path | None = None,
    title: str | None = None,
) -> str:
    """決済手段別のsummary.mdを生成

    Args:
        receipts: レシートリスト
        output_path: 出力先パス (Noneの場合は文字列のみ返す)
        title: サマリーのタイトル

    Returns:
        生成されたMarkdown文字列
    """
    if not receipts:
        return ""

    # ソース名を取得
    sources = {r.source for r in receipts}
    source_label = "/".join(s.value.upper() for s in sorted(sources, key=lambda s: s.value))

    if title is None:
        title = f"{source_label} レシート 分類結果"

    # 決済手段別にグループ化
    by_method: dict[str, list[Receipt]] = {}
    for r in receipts:
        method = r.payment_method.value
        if method not in by_method:
            by_method[method] = []
        by_method[method].append(r)

    lines = [f"# {title}", ""]

    for method, items in sorted(by_method.items()):
        lines.append(f"## {method}")
        lines.append("| 日付 | 金額 | ファイル |")
        lines.append("|------|------|----------|")
        total_amount = 0
        for item in sorted(items, key=lambda x: x.date):
            date_str = item.date.strftime("%Y-%m-%d")
            amount_str = f"¥{item.amount:,}"
            lines.append(f"| {date_str} | {amount_str} | {item.filename} |")
            total_amount += item.amount
        lines.append(f"\n**小計: {len(items)}件 ¥{total_amount:,}**")
        lines.append("")

    # 合計
    lines.append("## 合計")
    grand_total = 0
    for method, items in sorted(by_method.items()):
        method_total = sum(r.amount for r in items)
        grand_total += method_total
        lines.append(f"- {method}: {len(items)}件 ¥{method_total:,}")
    lines.append(f"- **総合計: {len(receipts)}件 ¥{grand_total:,}**")

    summary = "\n".join(lines)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(summary, encoding="utf-8")

    return summary


def save_results_json(
    receipts: list[Receipt],
    output_path: Path,
) -> None:
    """results.jsonを生成"""
    data = [r.to_dict() for r in receipts]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
