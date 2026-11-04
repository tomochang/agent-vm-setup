"""
doc-converter — ドキュメント変換パイプライン
PDF / DOCX / XLSX / HTML → Markdown

Usage:
    python3 convert.py <input_file> [--output output.md] [--format markdown|text]
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Optional dependency flags
# ---------------------------------------------------------------------------
class _DocxStub:
    """Stub so convert.docx.Document is always patchable."""

    class Document:
        pass


try:
    import docx  # python-docx

    DOCX_AVAILABLE = True
except ImportError:
    docx = _DocxStub()  # type: ignore[assignment]
    DOCX_AVAILABLE = False


class _OpenpyxlStub:
    """Stub so convert.openpyxl.load_workbook is always patchable."""

    @staticmethod
    def load_workbook(*args, **kwargs):
        raise ImportError("openpyxl not installed")


try:
    import openpyxl

    OPENPYXL_AVAILABLE = True
except ImportError:
    openpyxl = _OpenpyxlStub()  # type: ignore[assignment]
    OPENPYXL_AVAILABLE = False

INSTALL_HINT = (
    "\nRun `bash skills/doc-converter/scripts/install.sh` to install dependencies."
)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------
class UnsupportedFormatError(ValueError):
    """Raised when the file extension is not supported."""


class DependencyError(RuntimeError):
    """Raised when a required external dependency is missing."""


class ConversionError(RuntimeError):
    """Raised when the conversion process fails."""


# ---------------------------------------------------------------------------
# Converter registry
# ---------------------------------------------------------------------------
_EXT_MAP: dict[str, type] = {}


def _register(*exts):
    def decorator(cls):
        for ext in exts:
            _EXT_MAP[ext.lower()] = cls
        return cls

    return decorator


def get_converter(filename: str):
    """Return the appropriate converter for the given filename."""
    ext = Path(filename).suffix.lower()
    if ext not in _EXT_MAP:
        raise UnsupportedFormatError(
            f"Unsupported format: '{ext}'. "
            f"Supported: {', '.join(sorted(_EXT_MAP.keys()))}.{INSTALL_HINT}"
        )
    return _EXT_MAP[ext]()


# ---------------------------------------------------------------------------
# PDF Converter
# ---------------------------------------------------------------------------
@_register(".pdf")
class PdfConverter:
    """Extract text from PDF using pdftotext (poppler-utils)."""

    def convert(self, filepath: str) -> str:
        try:
            result = subprocess.run(
                ["pdftotext", "-layout", filepath, "-"],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            raise DependencyError(
                "pdftotext not found. Install poppler-utils." + INSTALL_HINT
            )

        if result.returncode != 0:
            raise ConversionError(
                f"pdftotext failed (exit {result.returncode}): {result.stderr.strip()}"
            )

        return self._structure(result.stdout)

    def _structure(self, raw: str) -> str:
        """Turn raw pdftotext output into structured Markdown."""
        lines = raw.splitlines()
        output: list[str] = []
        prev_blank = True

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if not prev_blank:
                    output.append("")
                prev_blank = True
                continue

            # Heuristic: short lines (< 60 chars) at start of a paragraph → heading
            if prev_blank and len(stripped) < 60 and not stripped.endswith("."):
                output.append(f"## {stripped}")
            else:
                output.append(stripped)
            prev_blank = False

        return "\n".join(output).strip()


# ---------------------------------------------------------------------------
# DOCX Converter
# ---------------------------------------------------------------------------
@_register(".docx", ".doc")
class DocxConverter:
    """Convert DOCX to Markdown using python-docx (or pandoc as fallback)."""

    _HEADING_MAP = {
        "Heading 1": "#",
        "Heading 2": "##",
        "Heading 3": "###",
        "Heading 4": "####",
        "Heading 5": "#####",
    }

    def convert(self, filepath: str) -> str:
        if DOCX_AVAILABLE:
            return self._convert_with_docx(filepath)
        return self._convert_with_pandoc(filepath)

    def _convert_with_docx(self, filepath: str) -> str:
        doc = docx.Document(filepath)
        output: list[str] = []

        for para in doc.paragraphs:
            text = para.text.strip()
            style_name = para.style.name if para.style else "Normal"
            if not text:
                output.append("")
                continue
            prefix = self._HEADING_MAP.get(style_name, "")
            if prefix:
                output.append(f"{prefix} {text}")
            else:
                output.append(text)

        for table in doc.tables:
            output.append("")
            output.extend(self._table_to_md(table))
            output.append("")

        return "\n".join(output).strip()

    def _table_to_md(self, table) -> list[str]:
        rows = []
        for i, row in enumerate(table.rows):
            cells = [cell.text.replace("|", "\\|").strip() for cell in row.cells]
            rows.append("| " + " | ".join(cells) + " |")
            if i == 0:
                rows.append("| " + " | ".join(["---"] * len(cells)) + " |")
        return rows

    def _convert_with_pandoc(self, filepath: str) -> str:
        try:
            result = subprocess.run(
                ["pandoc", "--from=docx", "--to=markdown", filepath],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            raise DependencyError(
                "Neither python-docx nor pandoc is installed." + INSTALL_HINT
            )
        if result.returncode != 0:
            raise ConversionError(f"pandoc failed: {result.stderr.strip()}")
        return result.stdout.strip()


# ---------------------------------------------------------------------------
# XLSX Converter
# ---------------------------------------------------------------------------
@_register(".xlsx", ".xls")
class XlsxConverter:
    """Convert XLSX sheets to Markdown tables using openpyxl."""

    def convert(self, filepath: str) -> str:
        if not OPENPYXL_AVAILABLE:
            raise DependencyError(
                "openpyxl is not installed. Install it with: pip install openpyxl"
                + INSTALL_HINT
            )
        wb = openpyxl.load_workbook(filepath, data_only=True)
        sections: list[str] = []

        for ws in wb.worksheets:
            rows = list(ws.iter_rows(values_only=False))
            if not rows:
                continue

            sections.append(f"## {ws.title}\n")
            md_rows: list[str] = []
            for i, row in enumerate(rows):
                cells = [str(cell.value) if cell.value is not None else "" for cell in row]
                md_rows.append("| " + " | ".join(cells) + " |")
                if i == 0:
                    md_rows.append("| " + " | ".join(["---"] * len(cells)) + " |")
            sections.append("\n".join(md_rows))

        return "\n\n".join(sections).strip()


# ---------------------------------------------------------------------------
# HTML Converter (built-in, no external deps)
# ---------------------------------------------------------------------------
@_register(".html", ".htm")
class HtmlConverter:
    """Convert HTML to Markdown using stdlib html.parser."""

    def convert(self, filepath: str) -> str:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            html = f.read()
        return self.convert_string(html)

    def convert_string(self, html: str) -> str:
        parser = _HtmlToMarkdown()
        parser.feed(html)
        return parser.get_markdown()


class _HtmlToMarkdown(HTMLParser):
    """Stateful HTML → Markdown parser."""

    _HEADING_LEVEL = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}

    def __init__(self):
        super().__init__()
        self._output: list[str] = []
        self._stack: list[str] = []
        self._list_counters: list[int] = []   # >0 = ordered, 0 = unordered
        self._in_table_header = False
        self._current_row: list[str] = []
        self._table_rows: list[list[str]] = []
        self._buf = ""

    # -- helpers -----------------------------------------------------------

    def _flush_buf(self):
        if self._buf.strip():
            self._output.append(self._buf.strip())
        self._buf = ""

    def _current_tag(self):
        return self._stack[-1] if self._stack else ""

    def _in_tag(self, *tags):
        return any(t in self._stack for t in tags)

    # -- HTMLParser interface -----------------------------------------------

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        self._stack.append(tag)

        if tag in self._HEADING_LEVEL:
            self._flush_buf()
            self._buf = "#" * self._HEADING_LEVEL[tag] + " "

        elif tag == "p":
            self._flush_buf()

        elif tag in ("strong", "b"):
            self._buf += "**"

        elif tag in ("em", "i"):
            self._buf += "*"

        elif tag == "code":
            self._buf += "`"

        elif tag == "a":
            href = attrs_dict.get("href", "")
            self._buf += f"["  # text follows, close bracket in endtag

        elif tag == "ul":
            self._flush_buf()
            self._list_counters.append(0)

        elif tag == "ol":
            self._flush_buf()
            self._list_counters.append(1)

        elif tag == "li":
            if self._list_counters:
                if self._list_counters[-1] == 0:
                    self._buf += "- "
                else:
                    n = self._list_counters[-1]
                    self._buf += f"{n}. "
                    self._list_counters[-1] += 1

        elif tag in ("table",):
            self._flush_buf()
            self._table_rows = []

        elif tag == "tr":
            self._current_row = []

        elif tag == "th":
            self._in_table_header = True

        elif tag == "td":
            self._in_table_header = False

        elif tag == "br":
            self._buf += "\n"

    def handle_endtag(self, tag):
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()

        if tag in self._HEADING_LEVEL:
            self._flush_buf()

        elif tag == "p":
            self._flush_buf()

        elif tag in ("strong", "b"):
            self._buf += "**"

        elif tag in ("em", "i"):
            self._buf += "*"

        elif tag == "code":
            self._buf += "`"

        elif tag == "a":
            # buf currently ends with "[text" — need to grab the href
            # We store href in handle_starttag via a sentinel approach
            # Simple approach: just close the bracket group
            # (href was already added as prefix; see handle_starttag)
            # We need to reconstruct: find last "[" in buf
            idx = self._buf.rfind("[")
            if idx >= 0:
                text = self._buf[idx + 1:]
                prefix = self._buf[:idx]
                # We don't have href here anymore; store it differently
                # Workaround: use _pending_href
                href = getattr(self, "_pending_href", "")
                self._buf = prefix + f"[{text}]({href})"
            self._pending_href = ""

        elif tag in ("ul", "ol"):
            if self._list_counters:
                self._list_counters.pop()
            self._flush_buf()

        elif tag == "li":
            self._flush_buf()

        elif tag in ("tr",):
            if self._current_row is not None:
                self._table_rows.append(self._current_row)
            self._current_row = []

        elif tag in ("th", "td"):
            self._current_row.append(self._buf.strip())
            self._buf = ""

        elif tag == "table":
            self._render_table()

    def handle_data(self, data):
        tag = self._current_tag()
        if tag in ("script", "style"):
            return
        # For table cells, accumulate into buf
        if self._in_tag("th", "td"):
            self._buf += data
            return
        self._buf += data

    def handle_starttag_a_href(self, href):
        self._pending_href = href

    def _render_table(self):
        if not self._table_rows:
            return
        lines = []
        for i, row in enumerate(self._table_rows):
            lines.append("| " + " | ".join(row) + " |")
            if i == 0:
                lines.append("| " + " | ".join(["---"] * len(row)) + " |")
        self._output.append("\n".join(lines))
        self._table_rows = []

    def get_markdown(self) -> str:
        self._flush_buf()
        # Collapse triple+ blank lines
        text = "\n\n".join(line for line in self._output if line.strip())
        return text.strip()


# Override handle_starttag to capture href before super() processes
_orig_start = _HtmlToMarkdown.handle_starttag


def _patched_start(self, tag, attrs):
    if tag == "a":
        attrs_dict = dict(attrs)
        self._pending_href = attrs_dict.get("href", "")
    _orig_start(self, tag, attrs)


_HtmlToMarkdown.handle_starttag = _patched_start


# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------

def _check_path_allowed(path: str, allowed_dirs: list[str]) -> None:
    """Raise PermissionError if *path* is not under any of *allowed_dirs*."""
    real = os.path.realpath(path)
    for d in allowed_dirs:
        real_d = os.path.realpath(d)
        if real == real_d or real.startswith(real_d + os.sep):
            return
    raise PermissionError(
        f"Access denied: {path} is outside allowed directories"
    )


def _check_file_size(path: str, max_size_mb: int) -> None:
    """Raise ValueError if *path* exceeds *max_size_mb* megabytes."""
    size_bytes = os.path.getsize(path)
    size_mb = size_bytes / (1024 * 1024)
    if size_mb > max_size_mb:
        raise ValueError(
            f"File too large: {size_mb:.1f}MB exceeds {max_size_mb}MB limit"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def convert_file(
    filepath: str,
    output_path: Optional[str] = None,
    fmt: str = "markdown",
    allowed_dirs: "list[str] | None" = None,
    max_size_mb: "int | None" = None,
) -> str:
    """Convert a document file to Markdown (or plain text).

    Args:
        filepath: Path to the input document.
        output_path: If given, write result to this path (creates parent dirs).
        fmt: "markdown" (default) or "text" (strip Markdown syntax).
        allowed_dirs: If not None, restrict input/output paths to these dirs.
        max_size_mb: If not None, reject files larger than this many MB.

    Returns:
        The converted text string.
    """
    if allowed_dirs is not None:
        _check_path_allowed(filepath, allowed_dirs)
        if output_path is not None:
            _check_path_allowed(output_path, allowed_dirs)

    if max_size_mb is not None:
        _check_file_size(filepath, max_size_mb)

    converter = get_converter(filepath)
    result = converter.convert(filepath)

    if fmt == "text":
        result = _strip_markdown(result)

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(result, encoding="utf-8")

    return result


def _strip_markdown(text: str) -> str:
    """Remove common Markdown syntax to produce plain text."""
    # Remove heading markers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove bold/italic
    text = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", text)
    # Remove inline code
    text = re.sub(r"`(.+?)`", r"\1", text)
    # Remove links: [text](url) → text
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    # Remove table separators
    text = re.sub(r"^\|[-| :]+\|\s*$", "", text, flags=re.MULTILINE)
    # Remove leading pipe from table cells
    text = re.sub(r"^\|", "", text, flags=re.MULTILINE)
    text = re.sub(r"\|$", "", text, flags=re.MULTILINE)
    return text.strip()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Convert documents (PDF/DOCX/XLSX/HTML) to Markdown."
    )
    parser.add_argument("input", help="Input document file path")
    parser.add_argument("--output", "-o", help="Output Markdown file (default: stdout)")
    parser.add_argument(
        "--format",
        "-f",
        choices=["markdown", "text"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--allow-path",
        action="append",
        default=[],
        metavar="DIR",
        help="Additional allowed directory (can be specified multiple times)",
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=100,
        metavar="MB",
        help="Maximum input file size in MB (default: 100)",
    )
    args = parser.parse_args()

    allowed_dirs = ["/workspace"] + args.allow_path

    try:
        result = convert_file(
            args.input,
            output_path=args.output,
            fmt=args.format,
            allowed_dirs=allowed_dirs,
            max_size_mb=args.max_size,
        )
        if not args.output:
            print(result)
    except Exception as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
