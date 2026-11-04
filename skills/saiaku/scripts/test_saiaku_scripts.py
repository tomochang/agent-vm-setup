"""Tests for saiaku's helper scripts. Run: python3 -m unittest skills/saiaku/scripts/test_saiaku_scripts.py"""
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import check_quotes  # noqa: E402
import jpsearch  # noqa: E402


class ParseTest(unittest.TestCase):
    def test_komachi(self):
        page = '<a href="/topics/id/1234567/" class="x"><span>夫が失踪</span> した</a>'
        self.assertEqual(jpsearch.parse("komachi", page),
                         [("https://komachi.yomiuri.co.jp/topics/id/1234567/", "夫が失踪 した")])

    def test_chiebukuro(self):
        page = ('<a href="https://detail.chiebukuro.yahoo.co.jp/qa/question_detail/q1012345678?x=1">'
                '義実家に<b>金</b>を</a>')
        self.assertEqual(jpsearch.parse("chiebukuro", page),
                         [("https://detail.chiebukuro.yahoo.co.jp/qa/question_detail/q1012345678", "義実家に 金 を")])

    def test_anond_falls_back_to_bare_links(self):
        page = '<p><a href="/20261027123456">x</a></p>'
        self.assertEqual(jpsearch.parse("anond", page), [("https://anond.hatelabo.jp/20261027123456", "")])

    def test_note(self):
        body = json.dumps({"data": {"notes": {"contents": [
            {"user": {"urlname": "abc"}, "key": "n1f", "name": "離婚の記録"}]}}})
        self.assertEqual(jpsearch.parse("note", body), [("https://note.com/abc/n/n1f", "離婚の記録")])

    def test_unknown_site(self):
        with self.assertRaises(ValueError):
            jpsearch.parse("x", "")

    def test_dedupe_and_limit(self):
        rows = [("u1", "a"), ("u1", "b"), ("u2", "c"), ("u3", "d")]
        self.assertEqual(jpsearch.dedupe(rows, 2), [("u1", "a"), ("u2", "c")])


class CheckQuotesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        src = pathlib.Path(self.tmp.name)
        (src / "a.md").write_text("first line\n夫が突然いなくなった\nthird\n", encoding="utf-8")
        self.src = src

    def tearDown(self):
        self.tmp.cleanup()

    def test_ok(self):
        self.assertEqual(check_quotes.check("a.md:2「突然いなくなった」", self.src), [("OK", "a.md:2", "")])

    def test_line_range(self):
        self.assertEqual(check_quotes.check("a.md:1-2「line 夫が」", self.src), [("OK", "a.md:1", "")])

    def test_wrong_line_reports_where_found(self):
        self.assertEqual(check_quotes.check("a.md:3「突然」", self.src), [("BAD", "a.md:3", "found at [2]")])

    def test_line_numbers_match_grep_with_form_feed(self):
        # pdftotext output has \f page breaks; grep -n does not count them as lines
        (self.src / "p.txt").write_text("page1\fstill line1\nline2 4.4 組に 1 組\n", encoding="utf-8")
        self.assertEqual(check_quotes.check("p.txt:2「4.4 組に 1 組」", self.src), [("OK", "p.txt:2", "")])

    def test_missing_file(self):
        self.assertEqual(check_quotes.check("b.md:1「x」", self.src), [("NOFILE", "b.md", "")])


if __name__ == "__main__":
    unittest.main()
