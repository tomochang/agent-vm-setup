#!/usr/bin/env python3
"""check_quotes.py <patterns.md> <sources-dir>: checks every file:line「quote」 against that line of the original.

Prints OK / BAD (with the lines where the quote really is) / NOFILE. Exit 1 if anything is not OK.
"""
import pathlib
import re
import sys

REF = re.compile(r'([\w.\-]+):(\d+)(?:-(\d+))?「([^」]+)」')


def check(text, sources):
    results = []
    for m in REF.finditer(text):
        name, a, b, quote = m.group(1), int(m.group(2)), int(m.group(3) or m.group(2)), m.group(4)
        path = pathlib.Path(sources) / name
        if not path.exists():
            results.append(("NOFILE", name, ""))
            continue
        # split on \n only: splitlines() also breaks on \f (pdftotext page breaks) and drifts from grep -n
        lines = path.read_text(encoding="utf-8", errors="replace").split("\n")
        if quote in " ".join(lines[a - 1:b]):
            results.append(("OK", f"{name}:{a}", ""))
        else:
            found = [i + 1 for i, line in enumerate(lines) if quote in line][:3]
            results.append(("BAD", f"{name}:{a}", f"found at {found}"))
    return results


def main(argv):
    results = check(pathlib.Path(argv[1]).read_text(encoding="utf-8"), argv[2])
    for status, ref, note in results:
        if status != "OK":
            print(status, ref, note)
    print(f"{sum(r[0] == 'OK' for r in results)}/{len(results)} OK")
    return 0 if all(r[0] == "OK" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
