#!/usr/bin/env python3
"""
ocr.py — 画像/PDFからテキスト抽出するOCRスクリプト

使い方:
    python3 scripts/ocr.py <file_or_dir> [--lang jpn+eng] [--json] [--output /path]
    python3 scripts/ocr.py <file_or_dir> --allow-path /tmp --max-size 200

依存:
    tesseract-ocr, tesseract-ocr-jpn, poppler-utils
    pip: pytesseract, Pillow, pdf2image
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# サポート拡張子
# ---------------------------------------------------------------------------
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".gif", ".webp"}
PDF_EXTENSIONS = {".pdf"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | PDF_EXTENSIONS


# ---------------------------------------------------------------------------
# 依存チェック
# ---------------------------------------------------------------------------
def _require_tesseract() -> None:
    """tesseract が利用可能か確認。なければ RuntimeError"""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
    except Exception as e:
        raise RuntimeError(
            "Tesseract OCR が見つかりません。\n"
            "インストール方法: sudo apt-get install tesseract-ocr tesseract-ocr-jpn\n"
            f"詳細: {e}"
        ) from e


def _require_pillow() -> None:
    try:
        import PIL  # noqa: F401
    except ImportError as e:
        raise RuntimeError(
            "Pillow が見つかりません。pip install Pillow でインストールしてください。"
        ) from e


def _require_pdf2image() -> None:
    try:
        import pdf2image  # noqa: F401
    except ImportError as e:
        raise RuntimeError(
            "pdf2image が見つかりません。pip install pdf2image でインストールしてください。"
        ) from e


# ---------------------------------------------------------------------------
# セキュリティユーティリティ
# ---------------------------------------------------------------------------

def _validate_path(path: str, allowed_dirs: list[str]) -> None:
    """
    パスが許可されたディレクトリ配下かチェックする。

    Args:
        path: チェック対象のパス（相対パスも可）
        allowed_dirs: 許可するディレクトリのリスト

    Raises:
        PermissionError: パスが許可ディレクトリ外の場合
    """
    real = os.path.realpath(path)
    for allowed in allowed_dirs:
        allowed_real = os.path.realpath(allowed)
        if real == allowed_real or real.startswith(allowed_real + os.sep):
            return
    raise PermissionError(f"Access denied: {path} is outside allowed directories")


def _check_file_size(file_path: str, max_size_mb: int) -> None:
    """
    ファイルサイズが上限以内かチェックする。

    Args:
        file_path: チェック対象のファイルパス
        max_size_mb: 上限 (MB)

    Raises:
        ValueError: ファイルサイズが上限を超える場合
    """
    size_bytes = os.path.getsize(file_path)
    size_mb = size_bytes / (1024 * 1024)
    if size_mb > max_size_mb:
        raise ValueError(
            f"File too large: {size_mb:.1f}MB exceeds {max_size_mb}MB limit"
        )


# ---------------------------------------------------------------------------
# コア関数
# ---------------------------------------------------------------------------

def extract_text_from_image(image_path: str, lang: str = "jpn+eng") -> str:
    """
    画像ファイルからテキストを抽出して返す。

    Args:
        image_path: 画像ファイルパス（jpg/png/tiff等）
        lang: tesseract 言語コード（例: "jpn+eng", "eng"）

    Returns:
        抽出したテキスト文字列

    Raises:
        FileNotFoundError: ファイルが存在しない場合
        ValueError: サポートされていない拡張子の場合
        RuntimeError: tesseract が利用できない場合
    """
    path = Path(image_path)

    if not path.exists():
        raise FileNotFoundError(f"ファイルが見つかりません: {image_path}")

    ext = path.suffix.lower()
    if ext not in IMAGE_EXTENSIONS:
        raise ValueError(
            f"非対応 (unsupported) 形式: '{ext}'. "
            f"サポートされている形式: {sorted(IMAGE_EXTENSIONS)}"
        )

    _require_pillow()
    _require_tesseract()

    try:
        import pytesseract
        from PIL import Image

        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang=lang)
        return text
    except RuntimeError:
        raise
    except Exception as e:
        msg = str(e).lower()
        if "tesseract" in msg or "not installed" in msg or "not found" in msg:
            raise RuntimeError(
                f"Tesseract OCR エラー: {e}\n"
                "sudo apt-get install tesseract-ocr でインストールしてください。"
            ) from e
        raise


def extract_text_from_pdf(pdf_path: str, lang: str = "jpn+eng", dpi: int = 200) -> list[dict]:
    """
    PDF ファイルの各ページをOCRしてテキストを抽出する。

    Args:
        pdf_path: PDFファイルパス
        lang: tesseract 言語コード
        dpi: 変換解像度（高いほど精度が上がるが遅い）

    Returns:
        [{"page": 1, "text": "..."}, {"page": 2, "text": "..."}, ...]

    Raises:
        FileNotFoundError: ファイルが存在しない場合
        ValueError: PDF以外の拡張子の場合
        RuntimeError: tesseract / pdf2image が利用できない場合
    """
    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(f"ファイルが見つかりません: {pdf_path}")

    ext = path.suffix.lower()
    if ext not in PDF_EXTENSIONS:
        raise ValueError(
            f"非対応 (unsupported) 形式: '{ext}'. PDF ファイルを指定してください。"
        )

    _require_pillow()
    _require_tesseract()
    _require_pdf2image()

    import pdf2image
    import pytesseract

    try:
        images = pdf2image.convert_from_path(pdf_path, dpi=dpi)
    except Exception as e:
        raise RuntimeError(
            f"PDF→画像変換に失敗しました: {e}\n"
            "sudo apt-get install poppler-utils でインストールしてください。"
        ) from e

    results = []
    for page_num, img in enumerate(images, start=1):
        try:
            text = pytesseract.image_to_string(img, lang=lang)
        except Exception as e:
            msg = str(e).lower()
            if "tesseract" in msg:
                raise RuntimeError(f"Tesseract OCR エラー (page {page_num}): {e}") from e
            raise
        results.append({"page": page_num, "text": text})

    return results


def process_path(
    path: str,
    lang: str = "jpn+eng",
    output_json: bool = False,
    output_path: str | None = None,
    allowed_dirs: list[str] | None = None,
    max_size_mb: int | None = None,
) -> list[dict]:
    """
    ファイルまたはディレクトリを処理してOCR結果を返す。

    Args:
        path: ファイルまたはディレクトリパス
        lang: tesseract 言語コード
        output_json: JSON 形式で返す場合 True
        output_path: 出力ファイルパス（指定時はファイルへ保存）
        allowed_dirs: 許可するディレクトリのリスト。None なら制限なし（ライブラリ利用時）
        max_size_mb: ファイルサイズ上限 (MB)。None なら制限なし

    Returns:
        [{"file": "...", "text": "..."}, ...]  # 画像
        [{"file": "...", "pages": [{"page": 1, "text": "..."}]}, ...]  # PDF

    Raises:
        PermissionError: allowed_dirs が指定されていてパスがその外にある場合
        ValueError: ファイルサイズが max_size_mb を超える場合
    """
    # パスバリデーション（allowed_dirs が指定されている場合のみ）
    if allowed_dirs is not None:
        _validate_path(path, allowed_dirs)
        if output_path is not None:
            _validate_path(output_path, allowed_dirs)

    p = Path(path)
    results: list[dict] = []

    if p.is_dir():
        # ディレクトリ: サポート対象ファイルを再帰せず一覧処理
        files = sorted(
            f for f in p.iterdir()
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
        )
        for file in files:
            # ディレクトリ内の各ファイルもパスバリデーション
            if allowed_dirs is not None:
                _validate_path(str(file), allowed_dirs)
            result = _process_single_file(str(file), lang=lang, max_size_mb=max_size_mb)
            if result is not None:
                results.append(result)
    elif p.is_file():
        result = _process_single_file(str(p), lang=lang, max_size_mb=max_size_mb)
        if result is not None:
            results.append(result)
    else:
        raise FileNotFoundError(f"パスが存在しません: {path}")

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    return results


def _process_single_file(
    file_path: str,
    lang: str,
    max_size_mb: int | None = None,
) -> dict | None:
    """単一ファイルを処理して結果辞書を返す。サポート外はNoneを返す。"""
    ext = Path(file_path).suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        return None  # サポート外はスキップ

    # ファイルサイズチェック
    if max_size_mb is not None:
        _check_file_size(file_path, max_size_mb)

    if ext in IMAGE_EXTENSIONS:
        text = extract_text_from_image(file_path, lang=lang)
        return {"file": file_path, "text": text}
    elif ext in PDF_EXTENSIONS:
        pages = extract_text_from_pdf(file_path, lang=lang)
        return {"file": file_path, "pages": pages}
    else:
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="画像/PDFからテキストを抽出するOCRツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python3 ocr.py image.png
  python3 ocr.py document.pdf --lang jpn+eng --json
  python3 ocr.py ./images/ --lang eng --output result.json
  python3 ocr.py image.png --allow-path /tmp --max-size 200
        """,
    )
    parser.add_argument("path", help="画像ファイル、PDFファイル、またはディレクトリ")
    parser.add_argument(
        "--lang", default="jpn+eng",
        help="tesseract 言語コード (デフォルト: jpn+eng)"
    )
    parser.add_argument(
        "--json", action="store_true", dest="output_json",
        help="JSON形式で出力する"
    )
    parser.add_argument(
        "--output", default=None, dest="output_path",
        help="出力ファイルパス（省略時は stdout）"
    )
    parser.add_argument(
        "--allow-path", action="append", default=[], dest="allow_path",
        metavar="DIR",
        help="アクセスを許可する追加ディレクトリ（複数指定可）"
    )
    parser.add_argument(
        "--max-size", type=int, default=100, dest="max_size",
        metavar="MB",
        help="ファイルサイズ上限 MB (デフォルト: 100)"
    )

    args = parser.parse_args()

    # tesseract の存在チェック（早期フェイル）
    try:
        _require_tesseract()
    except RuntimeError as e:
        print(f"RuntimeError: {e}", file=sys.stderr)
        sys.exit(1)

    # CLI では /workspace + --allow-path で許可ディレクトリを構築
    allowed_dirs = ["/workspace"] + args.allow_path

    try:
        results = process_path(
            args.path,
            lang=args.lang,
            output_json=args.output_json,
            output_path=args.output_path,
            allowed_dirs=allowed_dirs,
            max_size_mb=args.max_size,
        )

        if args.output_path:
            print(f"結果を {args.output_path} に保存しました。({len(results)} 件処理)")
        elif args.output_json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            # プレーンテキスト出力
            for item in results:
                print(f"=== {item['file']} ===")
                if "text" in item:
                    print(item["text"])
                elif "pages" in item:
                    for page in item["pages"]:
                        print(f"--- Page {page['page']} ---")
                        print(page["text"])
                print()

    except PermissionError as e:
        print(f"PermissionError: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"FileNotFoundError: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"ValueError: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"RuntimeError: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
