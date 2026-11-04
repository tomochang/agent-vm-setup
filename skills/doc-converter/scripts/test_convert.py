"""
TDD tests for doc-converter skill.
All tests use mocks so they pass without external dependencies.
"""
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

# Add scripts dir to path
sys.path.insert(0, str(Path(__file__).parent))

import convert


class TestAutoDetectFormat(unittest.TestCase):
    """test_auto_detect_format — ファイル拡張子から変換器自動選択"""

    def test_pdf_extension(self):
        converter = convert.get_converter("document.pdf")
        self.assertIsInstance(converter, convert.PdfConverter)

    def test_docx_extension(self):
        converter = convert.get_converter("document.docx")
        self.assertIsInstance(converter, convert.DocxConverter)

    def test_doc_extension(self):
        converter = convert.get_converter("document.doc")
        self.assertIsInstance(converter, convert.DocxConverter)

    def test_xlsx_extension(self):
        converter = convert.get_converter("spreadsheet.xlsx")
        self.assertIsInstance(converter, convert.XlsxConverter)

    def test_xls_extension(self):
        converter = convert.get_converter("spreadsheet.xls")
        self.assertIsInstance(converter, convert.XlsxConverter)

    def test_html_extension(self):
        converter = convert.get_converter("page.html")
        self.assertIsInstance(converter, convert.HtmlConverter)

    def test_htm_extension(self):
        converter = convert.get_converter("page.htm")
        self.assertIsInstance(converter, convert.HtmlConverter)

    def test_case_insensitive(self):
        converter = convert.get_converter("DOCUMENT.PDF")
        self.assertIsInstance(converter, convert.PdfConverter)


class TestUnsupportedFormat(unittest.TestCase):
    """test_unsupported_format — 非対応ファイルのエラーハンドリング"""

    def test_unknown_extension(self):
        with self.assertRaises(convert.UnsupportedFormatError) as ctx:
            convert.get_converter("file.xyz")
        self.assertIn(".xyz", str(ctx.exception))

    def test_no_extension(self):
        with self.assertRaises(convert.UnsupportedFormatError):
            convert.get_converter("README")

    def test_error_message_includes_install_hint(self):
        """非対応フォーマットでもinstall.shのヒントを出す"""
        try:
            convert.get_converter("file.xyz")
        except convert.UnsupportedFormatError as e:
            self.assertIn("install.sh", str(e))


class TestPdfToMarkdown(unittest.TestCase):
    """test_pdf_to_markdown — PDFテキスト抽出（pdftotext モック）"""

    def test_pdf_converts_to_markdown(self):
        """pdftotextの出力をMarkdownに変換"""
        sample_text = "Title\n\nThis is paragraph one.\n\nThis is paragraph two.\n"
        with patch("convert.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=sample_text, stderr=""
            )
            converter = convert.PdfConverter()
            result = converter.convert("dummy.pdf")
        self.assertIn("Title", result)
        self.assertIn("paragraph one", result)
        self.assertIn("paragraph two", result)

    def test_pdf_pdftotext_not_found(self):
        """pdftotext未インストール時は明確なエラー"""
        with patch("convert.subprocess.run", side_effect=FileNotFoundError):
            converter = convert.PdfConverter()
            with self.assertRaises(convert.DependencyError) as ctx:
                converter.convert("dummy.pdf")
        self.assertIn("pdftotext", str(ctx.exception))
        self.assertIn("install.sh", str(ctx.exception))

    def test_pdf_pdftotext_nonzero_exit(self):
        """pdftotext失敗時はエラー"""
        with patch("convert.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="Error: Syntax Error"
            )
            converter = convert.PdfConverter()
            with self.assertRaises(convert.ConversionError):
                converter.convert("dummy.pdf")

    def test_pdf_heading_detection(self):
        """短い行はHeadingとして扱う"""
        sample_text = "Introduction\n\nSome detailed content here.\n"
        with patch("convert.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=sample_text, stderr=""
            )
            converter = convert.PdfConverter()
            result = converter.convert("dummy.pdf")
        # Short lines should become headings
        self.assertRegex(result, r"#+\s+Introduction")


class TestDocxToMarkdown(unittest.TestCase):
    """test_docx_to_markdown — DOCXパース（python-docx or pandoc fallback）"""

    @staticmethod
    def _para(text: str, style_name: str):
        """Helper: create a paragraph mock with proper .style.name attribute."""
        style = MagicMock()
        style.name = style_name  # Must set as attribute, NOT MagicMock(name=...) which sets repr
        para = MagicMock()
        para.text = text
        para.style = style
        return para

    def test_docx_converts_paragraphs(self):
        """python-docxでパース → Markdown"""
        mock_doc = MagicMock()
        mock_doc.paragraphs = [
            self._para("Hello World", "Heading 1"),
            self._para("This is body text.", "Normal"),
            self._para("", "Normal"),
        ]
        mock_doc.tables = []

        with patch("convert.DOCX_AVAILABLE", True), patch(
            "convert.docx.Document", return_value=mock_doc
        ):
            converter = convert.DocxConverter()
            result = converter.convert("dummy.docx")

        self.assertIn("Hello World", result)
        self.assertIn("This is body text", result)

    def test_docx_heading_styles(self):
        """Heading 1/2/3 → Markdown #/##/###"""
        mock_doc = MagicMock()
        mock_doc.paragraphs = [
            self._para("Chapter 1", "Heading 1"),
            self._para("Section 1.1", "Heading 2"),
            self._para("Subsection", "Heading 3"),
            self._para("Body text here.", "Normal"),
        ]
        mock_doc.tables = []

        with patch("convert.DOCX_AVAILABLE", True), patch(
            "convert.docx.Document", return_value=mock_doc
        ):
            converter = convert.DocxConverter()
            result = converter.convert("dummy.docx")

        self.assertIn("# Chapter 1", result)
        self.assertIn("## Section 1.1", result)
        self.assertIn("### Subsection", result)

    def test_docx_table_to_markdown(self):
        """DOCXテーブル → Markdownテーブル"""
        mock_cell_a1 = MagicMock()
        mock_cell_a1.text = "Name"
        mock_cell_b1 = MagicMock()
        mock_cell_b1.text = "Age"
        mock_cell_a2 = MagicMock()
        mock_cell_a2.text = "Alice"
        mock_cell_b2 = MagicMock()
        mock_cell_b2.text = "30"

        mock_row1 = MagicMock()
        mock_row1.cells = [mock_cell_a1, mock_cell_b1]
        mock_row2 = MagicMock()
        mock_row2.cells = [mock_cell_a2, mock_cell_b2]

        mock_table = MagicMock()
        mock_table.rows = [mock_row1, mock_row2]

        mock_doc = MagicMock()
        mock_doc.paragraphs = []
        mock_doc.tables = [mock_table]

        with patch("convert.DOCX_AVAILABLE", True), patch(
            "convert.docx.Document", return_value=mock_doc
        ):
            converter = convert.DocxConverter()
            result = converter.convert("dummy.docx")

        self.assertIn("| Name |", result)
        self.assertIn("| Age |", result)
        self.assertIn("| Alice |", result)

    def test_docx_fallback_to_pandoc(self):
        """python-docx未インストール時はpandocにfallback"""
        pandoc_output = "# Hello\n\nBody text.\n"
        with patch("convert.DOCX_AVAILABLE", False), patch(
            "convert.subprocess.run"
        ) as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=pandoc_output, stderr=""
            )
            converter = convert.DocxConverter()
            result = converter.convert("dummy.docx")
        self.assertIn("Hello", result)

    def test_docx_no_deps_raises_error(self):
        """python-docxもpandocも無い時はDependencyError"""
        with patch("convert.DOCX_AVAILABLE", False), patch(
            "convert.subprocess.run", side_effect=FileNotFoundError
        ):
            converter = convert.DocxConverter()
            with self.assertRaises(convert.DependencyError) as ctx:
                converter.convert("dummy.docx")
        self.assertIn("install.sh", str(ctx.exception))


class TestXlsxToMarkdown(unittest.TestCase):
    """test_xlsx_to_markdown — XLSXをMarkdownテーブルに変換"""

    def test_xlsx_simple_table(self):
        """シンプルなXLSXシート → Markdownテーブル"""
        mock_ws = MagicMock()
        mock_ws.title = "Sheet1"
        mock_ws.iter_rows = MagicMock(
            return_value=[
                [MagicMock(value="Name"), MagicMock(value="Score")],
                [MagicMock(value="Alice"), MagicMock(value=95)],
                [MagicMock(value="Bob"), MagicMock(value=87)],
            ]
        )
        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Sheet1"]
        mock_wb.__getitem__ = MagicMock(return_value=mock_ws)
        mock_wb.worksheets = [mock_ws]

        with patch("convert.OPENPYXL_AVAILABLE", True), patch(
            "convert.openpyxl.load_workbook", return_value=mock_wb
        ):
            converter = convert.XlsxConverter()
            result = converter.convert("dummy.xlsx")

        self.assertIn("| Name |", result)
        self.assertIn("| Score |", result)
        self.assertIn("| Alice |", result)
        self.assertIn("| 95 |", result)

    def test_xlsx_separator_row(self):
        """ヘッダー行の後に separator row (|---|) が入る"""
        mock_ws = MagicMock()
        mock_ws.title = "Data"
        mock_ws.iter_rows = MagicMock(
            return_value=[
                [MagicMock(value="Col1"), MagicMock(value="Col2")],
                [MagicMock(value="val1"), MagicMock(value="val2")],
            ]
        )
        mock_wb = MagicMock()
        mock_wb.worksheets = [mock_ws]

        with patch("convert.OPENPYXL_AVAILABLE", True), patch(
            "convert.openpyxl.load_workbook", return_value=mock_wb
        ):
            converter = convert.XlsxConverter()
            result = converter.convert("dummy.xlsx")

        self.assertIn("| --- |", result)

    def test_xlsx_multiple_sheets(self):
        """複数シート → それぞれMarkdownセクションに"""
        mock_ws1 = MagicMock()
        mock_ws1.title = "Sheet1"
        mock_ws1.iter_rows = MagicMock(
            return_value=[[MagicMock(value="A"), MagicMock(value="B")]]
        )
        mock_ws2 = MagicMock()
        mock_ws2.title = "Sheet2"
        mock_ws2.iter_rows = MagicMock(
            return_value=[[MagicMock(value="X"), MagicMock(value="Y")]]
        )
        mock_wb = MagicMock()
        mock_wb.worksheets = [mock_ws1, mock_ws2]

        with patch("convert.OPENPYXL_AVAILABLE", True), patch(
            "convert.openpyxl.load_workbook", return_value=mock_wb
        ):
            converter = convert.XlsxConverter()
            result = converter.convert("dummy.xlsx")

        self.assertIn("Sheet1", result)
        self.assertIn("Sheet2", result)

    def test_xlsx_no_openpyxl_raises_error(self):
        """openpyxl未インストール時はDependencyError"""
        with patch("convert.OPENPYXL_AVAILABLE", False):
            converter = convert.XlsxConverter()
            with self.assertRaises(convert.DependencyError) as ctx:
                converter.convert("dummy.xlsx")
        self.assertIn("openpyxl", str(ctx.exception))
        self.assertIn("install.sh", str(ctx.exception))


class TestHtmlToMarkdown(unittest.TestCase):
    """test_html_to_markdown — HTMLをMarkdownに変換"""

    def test_html_headings(self):
        """h1/h2/h3 → #/##/###"""
        html = "<h1>Title</h1><h2>Section</h2><p>Content here.</p>"
        converter = convert.HtmlConverter()
        result = converter.convert_string(html)
        self.assertIn("# Title", result)
        self.assertIn("## Section", result)
        self.assertIn("Content here", result)

    def test_html_paragraphs(self):
        """<p>タグ → テキスト段落"""
        html = "<p>First paragraph.</p><p>Second paragraph.</p>"
        converter = convert.HtmlConverter()
        result = converter.convert_string(html)
        self.assertIn("First paragraph", result)
        self.assertIn("Second paragraph", result)

    def test_html_bold_italic(self):
        """<strong>/<b> → **bold**, <em>/<i> → *italic*"""
        html = "<p><strong>bold text</strong> and <em>italic text</em></p>"
        converter = convert.HtmlConverter()
        result = converter.convert_string(html)
        self.assertIn("**bold text**", result)
        self.assertIn("*italic text*", result)

    def test_html_links(self):
        """<a href="..."> → [text](url)"""
        html = '<p><a href="https://example.com">Example</a></p>'
        converter = convert.HtmlConverter()
        result = converter.convert_string(html)
        self.assertIn("[Example](https://example.com)", result)

    def test_html_unordered_list(self):
        """<ul><li> → - item"""
        html = "<ul><li>Item 1</li><li>Item 2</li><li>Item 3</li></ul>"
        converter = convert.HtmlConverter()
        result = converter.convert_string(html)
        self.assertIn("- Item 1", result)
        self.assertIn("- Item 2", result)

    def test_html_ordered_list(self):
        """<ol><li> → 1. item"""
        html = "<ol><li>First</li><li>Second</li></ol>"
        converter = convert.HtmlConverter()
        result = converter.convert_string(html)
        self.assertIn("1. First", result)
        self.assertIn("2. Second", result)

    def test_html_table(self):
        """<table> → Markdownテーブル"""
        html = """
        <table>
            <tr><th>Name</th><th>Value</th></tr>
            <tr><td>Alice</td><td>100</td></tr>
        </table>
        """
        converter = convert.HtmlConverter()
        result = converter.convert_string(html)
        self.assertIn("| Name |", result)
        self.assertIn("| Value |", result)
        self.assertIn("| Alice |", result)

    def test_html_code(self):
        """<code> → `code`"""
        html = "<p>Use <code>print()</code> function.</p>"
        converter = convert.HtmlConverter()
        result = converter.convert_string(html)
        self.assertIn("`print()`", result)

    def test_html_file_conversion(self):
        """ファイルパスからHTMLを読み込んで変換"""
        html_content = "<h1>Test</h1><p>Hello world.</p>"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False
        ) as f:
            f.write(html_content)
            tmp_path = f.name
        try:
            converter = convert.HtmlConverter()
            result = converter.convert(tmp_path)
            self.assertIn("# Test", result)
            self.assertIn("Hello world", result)
        finally:
            os.unlink(tmp_path)


class TestOutputToFile(unittest.TestCase):
    """test_output_to_file — ファイル出力オプション"""

    def test_output_to_file(self):
        """--output オプションでMarkdownファイルに書き出す"""
        html = "<h1>Output Test</h1><p>Content.</p>"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False
        ) as f:
            f.write(html)
            input_path = f.name

        with tempfile.NamedTemporaryFile(
            suffix=".md", delete=False
        ) as f:
            output_path = f.name

        try:
            convert.convert_file(input_path, output_path=output_path)
            with open(output_path) as f:
                content = f.read()
            self.assertIn("Output Test", content)
        finally:
            os.unlink(input_path)
            os.unlink(output_path)

    def test_output_to_stdout_when_no_output(self):
        """--output なしの場合はstdoutに出力"""
        html = "<h1>Stdout Test</h1><p>Content.</p>"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False
        ) as f:
            f.write(html)
            input_path = f.name

        try:
            result = convert.convert_file(input_path)
            self.assertIn("Stdout Test", result)
        finally:
            os.unlink(input_path)

    def test_output_creates_parent_dirs(self):
        """出力先ディレクトリが存在しなければ作成する"""
        html = "<p>Test</p>"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False
        ) as f:
            f.write(html)
            input_path = f.name

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "subdir", "output.md")
            try:
                convert.convert_file(input_path, output_path=output_path)
                self.assertTrue(os.path.exists(output_path))
            finally:
                pass
        os.unlink(input_path)


class TestTextFormat(unittest.TestCase):
    """--format text オプション: Markdownマーカーなしのプレーンテキスト"""

    def test_text_format_no_hash(self):
        """text フォーマットでは # が出力されない"""
        html = "<h1>Title</h1><p>Content.</p>"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False
        ) as f:
            f.write(html)
            input_path = f.name
        try:
            result = convert.convert_file(input_path, fmt="text")
            self.assertNotIn("#", result)
            self.assertIn("Title", result)
        finally:
            os.unlink(input_path)


class TestSecurityValidation(unittest.TestCase):
    """Security: path traversal and file size limits."""

    def test_path_traversal_blocked(self):
        """/etc/passwd 等 workspace 外パスは PermissionError"""
        with self.assertRaises(PermissionError) as ctx:
            convert.convert_file(
                "/etc/passwd",
                allowed_dirs=["/workspace"],
            )
        self.assertIn("Access denied", str(ctx.exception))

    def test_allow_path_override(self):
        """--allow-path 指定時はそのディレクトリが許可される"""
        html = "<h1>Allowed</h1><p>Content.</p>"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, dir=tempfile.gettempdir()
        ) as f:
            f.write(html)
            tmp_path = f.name
        try:
            # Should NOT raise when the tmp dir is explicitly allowed
            result = convert.convert_file(
                tmp_path,
                allowed_dirs=[tempfile.gettempdir()],
            )
            self.assertIn("Allowed", result)
        finally:
            os.unlink(tmp_path)

    def test_file_size_limit(self):
        """ファイルサイズ上限超過で ValueError"""
        html = "<p>Hello</p>"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False
        ) as f:
            f.write(html)
            tmp_path = f.name
        try:
            with self.assertRaises(ValueError) as ctx:
                convert.convert_file(
                    tmp_path,
                    max_size_mb=0,  # 0 MB limit → any file fails
                )
            self.assertIn("exceeds", str(ctx.exception))
        finally:
            os.unlink(tmp_path)

    def test_library_mode_no_restriction(self):
        """allowed_dirs=None の場合は制限なし（ライブラリ互換性維持）"""
        html = "<h1>Library mode</h1>"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False
        ) as f:
            f.write(html)
            tmp_path = f.name
        try:
            # No PermissionError even though path is outside /workspace
            result = convert.convert_file(
                tmp_path,
                allowed_dirs=None,  # no restriction
            )
            self.assertIn("Library mode", result)
        finally:
            os.unlink(tmp_path)


if __name__ == "__main__":
    unittest.main()
