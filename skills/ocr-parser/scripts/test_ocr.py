"""
test_ocr.py — OCR parser スキルのテスト（TDD: 実装前に書く）

テスト実行:
    python3 -m pytest scripts/test_ocr.py -v
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# テスト対象モジュールのパスを追加
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

# PIL/Pillow が使えるかチェック
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

# pytesseract が使えるかチェック
try:
    import pytesseract
    pytesseract.get_tesseract_version()
    HAS_TESSERACT = True
except Exception:
    HAS_TESSERACT = False


# ============================================================
# ヘルパー
# ============================================================

def make_test_image_english(text: str, path: str) -> None:
    """英語テキスト入り PNG 画像を生成"""
    img = Image.new("RGB", (400, 100), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 30), text, fill="black")
    img.save(path)


def make_test_image_japanese(text: str, path: str) -> None:
    """日本語テキスト入り PNG 画像を生成（フォント未指定でも動く）"""
    img = Image.new("RGB", (400, 100), color="white")
    draw = ImageDraw.Draw(img)
    # システムフォントを試みる
    try:
        font = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 24)
    except Exception:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 24)
        except Exception:
            font = ImageFont.load_default()
    draw.text((10, 30), text, fill="black", font=font)
    img.save(path)


def make_test_pdf(text: str, path: str) -> None:
    """テスト用 PDF を reportlab または fpdf2 で生成。なければ PyMuPDF、最終的には skip"""
    try:
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(path)
        c.drawString(72, 720, text)
        c.save()
        return
    except ImportError:
        pass

    try:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=16)
        pdf.cell(200, 10, txt=text, ln=True)
        pdf.output(path)
        return
    except ImportError:
        pass

    pytest.skip("PDF生成ライブラリ(reportlab/fpdf2)が未インストール")


# ============================================================
# インポートテスト（実装前は ImportError になる → RED）
# ============================================================

def get_ocr_module():
    """ocr モジュールをインポート。失敗したら None を返す"""
    try:
        import ocr
        return ocr
    except ImportError:
        return None


# ============================================================
# テストクラス
# ============================================================


class TestOCRImport:
    """モジュールが正しくインポートできるか"""

    def test_module_importable(self):
        """ocr.py がインポートできること"""
        ocr = get_ocr_module()
        assert ocr is not None, "ocr.py が見つかりません。scripts/ocr.py を実装してください。"

    def test_required_functions_exist(self):
        """必要な関数が定義されていること"""
        ocr = get_ocr_module()
        assert ocr is not None
        assert hasattr(ocr, "extract_text_from_image"), "extract_text_from_image が未定義"
        assert hasattr(ocr, "extract_text_from_pdf"), "extract_text_from_pdf が未定義"
        assert hasattr(ocr, "process_path"), "process_path が未定義"


@pytest.mark.skipif(not HAS_PILLOW, reason="Pillow がインストールされていません")
@pytest.mark.skipif(not HAS_TESSERACT, reason="Tesseract がインストールされていません")
class TestExtractTextFromImage:
    """test_extract_text_from_image — 画像からのテキスト抽出"""

    def test_extract_text_from_image_returns_string(self, tmp_path):
        """extract_text_from_image が文字列を返すこと"""
        ocr = get_ocr_module()
        assert ocr is not None

        img_path = str(tmp_path / "test.png")
        make_test_image_english("Hello World", img_path)

        result = ocr.extract_text_from_image(img_path, lang="eng")
        assert isinstance(result, str), "戻り値が文字列ではありません"

    def test_extract_text_from_image_content(self, tmp_path):
        """画像内のテキストが抽出されること"""
        ocr = get_ocr_module()
        assert ocr is not None

        img_path = str(tmp_path / "test_hello.png")
        make_test_image_english("HELLO", img_path)

        result = ocr.extract_text_from_image(img_path, lang="eng")
        assert "HELLO" in result.upper(), f"'HELLO' が抽出結果に含まれていません: {result!r}"

    def test_extract_text_from_png(self, tmp_path):
        """PNG 形式をサポートすること"""
        ocr = get_ocr_module()
        assert ocr is not None

        img_path = str(tmp_path / "sample.png")
        make_test_image_english("TEST PNG", img_path)
        result = ocr.extract_text_from_image(img_path, lang="eng")
        assert isinstance(result, str)

    def test_extract_text_from_jpg(self, tmp_path):
        """JPEG 形式をサポートすること"""
        ocr = get_ocr_module()
        assert ocr is not None

        img = Image.new("RGB", (400, 100), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((10, 30), "TEST JPG", fill="black")
        img_path = str(tmp_path / "sample.jpg")
        img.save(img_path, format="JPEG")

        result = ocr.extract_text_from_image(img_path, lang="eng")
        assert isinstance(result, str)


@pytest.mark.skipif(not HAS_PILLOW, reason="Pillow がインストールされていません")
@pytest.mark.skipif(not HAS_TESSERACT, reason="Tesseract がインストールされていません")
class TestExtractTextFromPDF:
    """test_extract_text_from_pdf — PDF からのテキスト抽出"""

    def test_extract_text_from_pdf_returns_list(self, tmp_path):
        """extract_text_from_pdf がリストを返すこと"""
        ocr = get_ocr_module()
        assert ocr is not None

        pdf_path = str(tmp_path / "test.pdf")
        make_test_pdf("Hello PDF World", pdf_path)

        result = ocr.extract_text_from_pdf(pdf_path, lang="eng")
        assert isinstance(result, list), f"戻り値がリストではありません: {type(result)}"

    def test_extract_text_from_pdf_page_structure(self, tmp_path):
        """PDF 抽出結果が {page, text} 構造を持つこと"""
        ocr = get_ocr_module()
        assert ocr is not None

        pdf_path = str(tmp_path / "test_struct.pdf")
        make_test_pdf("Structure Test", pdf_path)

        result = ocr.extract_text_from_pdf(pdf_path, lang="eng")
        assert len(result) >= 1, "少なくとも1ページの結果が必要"
        page = result[0]
        assert "page" in page, "page キーが存在しません"
        assert "text" in page, "text キーが存在しません"
        assert page["page"] == 1, f"最初のページ番号が 1 ではありません: {page['page']}"

    def test_extract_text_from_pdf_with_mock(self, tmp_path):
        """pdf2image が利用できない場合のフォールバック（モック）"""
        ocr = get_ocr_module()
        assert ocr is not None

        pdf_path = str(tmp_path / "mock.pdf")
        # ダミー PDF ファイルを作成
        Path(pdf_path).write_bytes(b"%PDF-1.4 dummy")

        mock_img = Image.new("RGB", (200, 50), color="white")
        draw = ImageDraw.Draw(mock_img)
        draw.text((5, 10), "MOCKED", fill="black")

        with mock.patch("pdf2image.convert_from_path", return_value=[mock_img]):
            result = ocr.extract_text_from_pdf(pdf_path, lang="eng")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["page"] == 1


@pytest.mark.skipif(not HAS_PILLOW, reason="Pillow がインストールされていません")
@pytest.mark.skipif(not HAS_TESSERACT, reason="Tesseract がインストールされていません")
class TestJapaneseText:
    """test_japanese_text — 日本語テキスト抽出"""

    def test_japanese_lang_param_accepted(self, tmp_path):
        """lang='jpn' パラメータが受け付けられること"""
        ocr = get_ocr_module()
        assert ocr is not None

        img_path = str(tmp_path / "ja.png")
        make_test_image_japanese("テスト", img_path)
        # エラーなく完了することを確認（テキスト精度は問わない）
        result = ocr.extract_text_from_image(img_path, lang="jpn")
        assert isinstance(result, str)

    def test_japanese_combined_lang(self, tmp_path):
        """lang='jpn+eng' が受け付けられること"""
        ocr = get_ocr_module()
        assert ocr is not None

        img_path = str(tmp_path / "ja_en.png")
        make_test_image_japanese("Hello", img_path)
        result = ocr.extract_text_from_image(img_path, lang="jpn+eng")
        assert isinstance(result, str)


@pytest.mark.skipif(not HAS_PILLOW, reason="Pillow がインストールされていません")
@pytest.mark.skipif(not HAS_TESSERACT, reason="Tesseract がインストールされていません")
class TestJSONOutput:
    """test_json_output — JSON 出力形式の検証"""

    def test_process_path_image_json_structure(self, tmp_path):
        """process_path の JSON 出力が正しい構造を持つこと"""
        ocr = get_ocr_module()
        assert ocr is not None

        img_path = str(tmp_path / "json_test.png")
        make_test_image_english("JSON OUTPUT TEST", img_path)

        result = ocr.process_path(img_path, lang="eng", output_json=True)
        assert isinstance(result, list), "process_path は list を返すべき"
        assert len(result) >= 1

        item = result[0]
        assert "file" in item, "file キーが必要"
        assert "pages" in item or "text" in item, "pages または text キーが必要"

    def test_json_serializable(self, tmp_path):
        """process_path の結果が JSON シリアライズ可能なこと"""
        ocr = get_ocr_module()
        assert ocr is not None

        img_path = str(tmp_path / "serial_test.png")
        make_test_image_english("SERIALIZABLE", img_path)

        result = ocr.process_path(img_path, lang="eng", output_json=True)
        # json.dumps が例外なく完了すること
        serialized = json.dumps(result, ensure_ascii=False)
        assert isinstance(serialized, str)
        # デシリアライズして同一か確認
        decoded = json.loads(serialized)
        assert decoded == result

    def test_json_output_to_file(self, tmp_path):
        """--output 指定時にファイルへ保存されること"""
        ocr = get_ocr_module()
        assert ocr is not None

        img_path = str(tmp_path / "out_test.png")
        make_test_image_english("FILE OUTPUT", img_path)
        out_path = str(tmp_path / "output.json")

        ocr.process_path(img_path, lang="eng", output_json=True, output_path=out_path)
        assert Path(out_path).exists(), "出力ファイルが作成されていません"
        with open(out_path) as f:
            data = json.load(f)
        assert isinstance(data, list)


@pytest.mark.skipif(not HAS_PILLOW, reason="Pillow がインストールされていません")
@pytest.mark.skipif(not HAS_TESSERACT, reason="Tesseract がインストールされていません")
class TestBatchProcessing:
    """test_batch_processing — ディレクトリ一括処理"""

    def test_process_directory(self, tmp_path):
        """ディレクトリを渡すと全ファイルが処理されること"""
        ocr = get_ocr_module()
        assert ocr is not None

        # 2枚の画像を作成
        make_test_image_english("BATCH ONE", str(tmp_path / "img1.png"))
        make_test_image_english("BATCH TWO", str(tmp_path / "img2.png"))

        result = ocr.process_path(str(tmp_path), lang="eng", output_json=True)
        assert isinstance(result, list)
        assert len(result) == 2, f"2ファイル処理されるべき: {len(result)} 件"

    def test_batch_result_structure(self, tmp_path):
        """バッチ処理結果の各要素が file キーを持つこと"""
        ocr = get_ocr_module()
        assert ocr is not None

        make_test_image_english("STRUCT A", str(tmp_path / "a.png"))
        make_test_image_english("STRUCT B", str(tmp_path / "b.png"))

        result = ocr.process_path(str(tmp_path), lang="eng", output_json=True)
        for item in result:
            assert "file" in item, f"file キーが存在しません: {item}"

    def test_batch_skips_unsupported(self, tmp_path):
        """サポート外のファイルはスキップされること"""
        ocr = get_ocr_module()
        assert ocr is not None

        make_test_image_english("VALID", str(tmp_path / "valid.png"))
        (tmp_path / "ignore.txt").write_text("not an image")
        (tmp_path / "ignore.csv").write_text("a,b,c")

        result = ocr.process_path(str(tmp_path), lang="eng", output_json=True)
        # PNG のみ処理 (txt/csv はスキップ)
        assert len(result) == 1, f"PNG 1件のみ処理: {len(result)} 件処理されました"


class TestUnsupportedFormat:
    """test_unsupported_format — 非対応ファイルのエラーハンドリング"""

    def test_unsupported_extension_raises(self, tmp_path):
        """非対応拡張子でわかりやすい例外が発生すること"""
        ocr = get_ocr_module()
        assert ocr is not None

        txt_path = str(tmp_path / "test.txt")
        Path(txt_path).write_text("plain text")

        with pytest.raises(ValueError, match=r"(?i)unsupported|非対応|サポート"):
            ocr.extract_text_from_image(txt_path)

    def test_missing_tesseract_error_message(self, tmp_path):
        """tesseract が存在しない場合にわかりやすいエラーが出ること（モック）"""
        ocr = get_ocr_module()
        assert ocr is not None

        if not HAS_PILLOW:
            pytest.skip("Pillow が必要")

        img = Image.new("RGB", (100, 30), color="white")
        img_path = str(tmp_path / "notsseract.png")
        img.save(img_path)

        import pytesseract as pyt
        with mock.patch.object(pyt, "image_to_string",
                               side_effect=Exception("tesseract is not installed")):
            with pytest.raises(RuntimeError, match=r"(?i)tesseract"):
                ocr.extract_text_from_image(img_path, lang="eng")

    def test_nonexistent_file_raises(self, tmp_path):
        """存在しないファイルで FileNotFoundError が発生すること"""
        ocr = get_ocr_module()
        assert ocr is not None

        with pytest.raises(FileNotFoundError):
            ocr.extract_text_from_image(str(tmp_path / "ghost.png"))


class TestCLI:
    """CLI 実行テスト"""

    @pytest.mark.skipif(not HAS_PILLOW, reason="Pillow がインストールされていません")
    @pytest.mark.skipif(not HAS_TESSERACT, reason="Tesseract がインストールされていません")
    def test_cli_image_plain_text(self, tmp_path):
        """CLI でプレーンテキスト出力が得られること"""
        img_path = str(tmp_path / "cli_test.png")
        make_test_image_english("CLI TEST", img_path)

        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "ocr.py"), img_path, "--lang", "eng",
             "--allow-path", str(tmp_path)],
            capture_output=True, text=True
        )
        assert result.returncode == 0, f"CLI 実行失敗: {result.stderr}"
        assert isinstance(result.stdout, str)

    @pytest.mark.skipif(not HAS_PILLOW, reason="Pillow がインストールされていません")
    @pytest.mark.skipif(not HAS_TESSERACT, reason="Tesseract がインストールされていません")
    def test_cli_image_json_output(self, tmp_path):
        """CLI --json オプションで JSON が出力されること"""
        img_path = str(tmp_path / "cli_json.png")
        make_test_image_english("CLI JSON", img_path)

        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "ocr.py"), img_path, "--lang", "eng", "--json",
             "--allow-path", str(tmp_path)],
            capture_output=True, text=True
        )
        assert result.returncode == 0, f"CLI 実行失敗: {result.stderr}"
        data = json.loads(result.stdout)
        assert isinstance(data, list)

    def test_cli_missing_tesseract_shows_message(self, tmp_path):
        """tesseract 未インストール時にわかりやすいメッセージが表示されること"""
        img_path = str(tmp_path / "dummy.png")
        if HAS_PILLOW:
            Image.new("RGB", (100, 30), color="white").save(img_path)
        else:
            Path(img_path).write_bytes(b"fake")

        env = os.environ.copy()
        env["PATH"] = "/nonexistent"  # tesseract を見えなくする

        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "ocr.py"), img_path],
            capture_output=True, text=True, env=env
        )
        # エラー終了 かつ stderr にヒントが含まれる
        combined = result.stdout + result.stderr
        assert result.returncode != 0 or "tesseract" in combined.lower(), \
            f"tesseract エラーメッセージが不明瞭: {combined!r}"


# ============================================================
# セキュリティテスト
# ============================================================


class TestPathSecurity:
    """パスバリデーション・ファイルサイズ制限のテスト"""

    def test_path_traversal_blocked(self, tmp_path):
        """workspace 外パス（/etc/passwd 等）が PermissionError になること"""
        ocr = get_ocr_module()
        assert ocr is not None

        with pytest.raises(PermissionError, match="Access denied"):
            ocr.process_path(
                "/etc/passwd",
                allowed_dirs=["/workspace"],
            )

    def test_path_traversal_blocked_tmp(self, tmp_path):
        """/tmp 配下も workspace 外なら PermissionError になること"""
        ocr = get_ocr_module()
        assert ocr is not None

        # tmp_path は /tmp 配下。allowed_dirs に含まれていなければ拒否
        dummy = tmp_path / "dummy.png"
        dummy.write_bytes(b"fake")

        with pytest.raises(PermissionError, match="Access denied"):
            ocr.process_path(
                str(dummy),
                allowed_dirs=["/workspace"],
            )

    def test_allow_path_override(self, tmp_path):
        """--allow-path 指定時はそのディレクトリが許可されること"""
        ocr = get_ocr_module()
        assert ocr is not None

        if not HAS_PILLOW or not HAS_TESSERACT:
            # OCR 実行まで到達しなくても、PermissionError が出なければ OK
            dummy = tmp_path / "dummy.png"
            dummy.write_bytes(b"PNG\x89")
            # PermissionError が raise されなければ合格
            try:
                ocr.process_path(
                    str(dummy),
                    allowed_dirs=["/workspace", str(tmp_path)],
                )
            except PermissionError:
                pytest.fail("allow_path を指定したのに PermissionError が発生しました")
            except Exception:
                pass  # OCR 実行エラーは許容
        else:
            from PIL import Image as PILImage
            img = PILImage.new("RGB", (200, 50), color="white")
            img_path = tmp_path / "allowed.png"
            img.save(str(img_path))

            # PermissionError が出なければ合格（OCR 結果は問わない）
            try:
                result = ocr.process_path(
                    str(img_path),
                    lang="eng",
                    allowed_dirs=["/workspace", str(tmp_path)],
                )
                assert isinstance(result, list)
            except PermissionError:
                pytest.fail("allow_path を指定したのに PermissionError が発生しました")

    def test_file_size_limit(self, tmp_path):
        """ファイルサイズが上限を超えると ValueError になること"""
        ocr = get_ocr_module()
        assert ocr is not None

        # 2MB のダミーファイルを作成
        large_file = tmp_path / "large.png"
        large_file.write_bytes(b"\x00" * (2 * 1024 * 1024))

        with pytest.raises(ValueError, match="File too large"):
            ocr.process_path(
                str(large_file),
                allowed_dirs=None,   # パス制限なし
                max_size_mb=1,       # 1MB 上限 → 2MB で超過
            )

    def test_library_mode_no_restriction(self, tmp_path):
        """allowed_dirs=None なら制限なし（ライブラリとして使う場合の互換性）"""
        ocr = get_ocr_module()
        assert ocr is not None

        # /tmp 配下のファイルでも PermissionError が出ないこと
        dummy = tmp_path / "dummy.png"
        dummy.write_bytes(b"fake")  # 非画像でも FileNotFoundError 以外なら OK

        try:
            ocr.process_path(
                str(dummy),
                allowed_dirs=None,  # 制限なし
            )
        except PermissionError:
            pytest.fail("allowed_dirs=None なのに PermissionError が発生しました")
        except Exception:
            pass  # OCR 処理エラーは許容（ファイルが壊れているので）
