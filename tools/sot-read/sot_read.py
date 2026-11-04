#!/usr/bin/env python3
"""C3 SoT section reader: read clawd's human todo SoT efficiently.

Boundary rule (determined 2026-11-02 by inspecting the real
~/workspace/clawd/private/todo_log.md, 279,412 bytes):
  - Item sections are headed by a markdown heading whose text IS the item
    id, e.g. `## sch-1105-tawa`, `## sch-1010-manila`, `## kawanaka-fund`.
  - A section may contain deeper sub-headings (e.g. `### 2026-10-17 ...`
    dated entries under `## sch-1010-manila`); those belong to the section.
  - Archived items moved on 2026-10-28 appear as one level deeper:
    `### t1028-sg-trip (移設前 L5-7)` -- heading text STARTS with the id.
  - A section ends at the next heading of the same or higher level
    (fewer or equal '#') than its own heading.
So: a section start is a heading whose text equals the item id, or begins
with the item id followed by a non-id character. The section runs until
the next heading of level <= its own level.

Safety: if the id has no heading, or matches multiple headings that are
not one contiguous (nested) section, or the extracted section would be
more than half the whole file, this tool refuses with exit 2 and a
FALLBACK message on stderr telling the caller to do a full read. It never
prints the whole log for a section request.

Usage:
  sot_read.py full [--file PATH]          # default: clawd/private/todo.md
  sot_read.py log <item-id> [--file PATH] # default: clawd/private/todo_log.md

`full` writes the file byte-for-byte to stdout and its sha256 + byte
count to stderr. Python 3 stdlib only.
"""
import argparse
import hashlib
import re
import sys

import os
RECORDS_DIR = os.environ.get("RECORDS_DIR", os.path.expanduser("~/workspace/clawd"))
DEFAULT_TODO = os.environ.get("TODO_FILE", os.path.join(RECORDS_DIR, "private", "todo.md"))
DEFAULT_LOG = os.environ.get("TODO_LOG_FILE", os.path.join(RECORDS_DIR, "private", "todo_log.md"))

HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*$")
ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _is_id_char(ch):
    return ch.isalnum() or ch in "-_"


def cmd_full(path):
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as e:
        print("ERROR: cannot read %s: %s" % (path, e), file=sys.stderr)
        return 1
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()
    print("sha256=%s bytes=%d file=%s" % (
        hashlib.sha256(data).hexdigest(), len(data), path), file=sys.stderr)
    return 0


def fallback(item_id, reason):
    print("FALLBACK: %s (item=%r). Do a full read instead: "
          "sot_read.py full --file <log path> (or read the file directly) "
          "and locate the item manually." % (reason, item_id),
          file=sys.stderr)
    return 2


def cmd_log(item_id, path):
    if not item_id or not ID_RE.match(item_id):
        return fallback(item_id, "item id is empty or has unexpected "
                                 "characters")
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as e:
        print("ERROR: cannot read %s: %s" % (path, e), file=sys.stderr)
        return 1
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines(keepends=True)

    # Index headings: (line_idx, level, heading_text)
    headings = []
    for i, line in enumerate(lines):
        m = HEADING_RE.match(line.rstrip("\r\n"))
        if m:
            headings.append((i, len(m.group(1)), m.group(2)))

    def heading_matches(heading_text):
        if heading_text == item_id:
            return True
        # starts with the id followed by a non-id char, e.g.
        # "t1028-sg-trip (移設前 L5-7)" -- note ids themselves contain '-',
        # so require the boundary char to be outside [A-Za-z0-9_-].
        if heading_text.startswith(item_id):
            rest = heading_text[len(item_id):]
            return bool(rest) and not _is_id_char(rest[0])
        return False

    starts = [(i, lvl) for (i, lvl, txt) in headings if heading_matches(txt)]
    if not starts:
        body_mentions = sum(1 for ln in lines if item_id in ln)
        if body_mentions:
            return fallback(item_id,
                            "no section heading for this id, though it is "
                            "mentioned on %d line(s) in body text; a "
                            "section boundary cannot be determined safely"
                            % body_mentions)
        return fallback(item_id, "item id not found in the log (no heading, "
                                 "no mention)")

    def section_end(start_idx, level):
        for (i, lvl, _txt) in headings:
            if i > start_idx and lvl <= level:
                return i
        return len(lines)

    # One contiguous section iff every other start lies inside the first
    # (outermost) start's section.
    first_idx, first_lvl = starts[0]
    end = section_end(first_idx, first_lvl)
    if any(not (first_idx < i < end) for i, _lvl in starts[1:]):
        return fallback(item_id,
                        "ambiguous: %d headings match this id and they are "
                        "not one contiguous section" % len(starts))

    section = "".join(lines[first_idx:end])
    data = section.encode("utf-8")
    if len(data) * 2 > len(raw):
        return fallback(item_id,
                        "extracted section would be %d of %d bytes "
                        "(>50%% of the log); refusing to risk dumping the "
                        "whole log for a section request"
                        % (len(data), len(raw)))
    sys.stdout.write(section)
    sys.stdout.flush()
    print("section_bytes=%d file_bytes=%d lines=%d item=%s" % (
        len(data), len(raw), end - first_idx, item_id), file=sys.stderr)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_full = sub.add_parser("full", help="print the todo file byte-for-byte")
    p_full.add_argument("--file", default=DEFAULT_TODO)
    p_log = sub.add_parser("log", help="print only one item's log section")
    p_log.add_argument("item_id")
    p_log.add_argument("--file", default=DEFAULT_LOG)
    args = ap.parse_args(argv)
    if args.cmd == "full":
        return cmd_full(args.file)
    return cmd_log(args.item_id, args.file)


if __name__ == "__main__":
    sys.exit(main())
