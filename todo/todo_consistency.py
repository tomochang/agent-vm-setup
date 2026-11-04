#!/usr/bin/env python3
"""Three-line todo format checker (stdlib only).

Checks the format defined in todo-format.md: every open item in the
todo file is exactly 3 lines, line 2 carries the deadline / state /
last-checked fields, line 3 starts with the history marker and holds
no quoted text, and no finished item stays in the todo file.

With --base <git-rev>, only items added or changed against that
revision are judged, so the format can be adopted incrementally.
Without --base, every item is judged.

Usage:
  todo_consistency.py check [--root <records-repo>] [--file private/todo.md]
                            [--done-file private/todo_done.md] [--base origin/main]

Prints a JSON object {"errors": [...], "warnings": [...], "checked": n}
and exits 1 while errors exist.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ITEM_START = re.compile(r'^- \[ \]')
CHILD_START = re.compile(r'^\s+(?:[-*+]|\d+[.)])\s')
CHECKED = re.compile(r'(?:^|[｜|])\s*確認(?:\s*[:：]|\s+\S)|状態\s*[(（][^)）]*確認\s*[)）]\s*[:：]')
STATE_FIELD = re.compile(r'状態\s*(?:[(（][^)）]*[)）])?\s*[:：]')
CHAT_NAMES = ('Messenger', 'LINE', 'WhatsApp', 'Slack', 'Beeper', 'Instagram', 'Telegram',
              'Signal', 'iMessage', 'Facebook', 'Chatwork', 'Discord', 'Teams')
CHAT_END = re.compile(r'(?:' + '|'.join(re.escape(n) for n in CHAT_NAMES) + r')\s*$', re.I)
VERB_END = 'うくぐすつぬぶむる'
STATES = ('ready', 'waiting_external', 'waiting_user', 'waiting_precondition',
          'in_progress', 'done')


def _items(text):
    """Open top-level items: 1-based first line, key line, own and child lines."""
    lines = text.split('\n')
    items, i = [], 0
    while i < len(lines):
        if not ITEM_START.match(lines[i]):
            i += 1
            continue
        start, j = i, i + 1
        body = []
        while j < len(lines) and lines[j].strip() and lines[j][:1] in (' ', '\t'):
            body.append(lines[j])
            j += 1
        own, children, in_children = [lines[start]], [], False
        for line in body:
            if not in_children and CHILD_START.match(line):
                in_children = True
            (children if in_children else own).append(line)
        items.append({'line': start + 1, 'key': lines[start].rstrip(),
                      'block': '\n'.join(x.rstrip() for x in own + children),
                      'own': own, 'children': children})
        i = j
    return items


def _title(line):
    m = re.search(r'\*\*(.*?)\*\*', line)
    text = m.group(1) if m else re.sub(r'<!--.*?-->', '', re.sub(r'^- \[ \] ', '', line))
    return text.strip().rstrip('。．.！!')


def _has_quote(line):
    for m in re.finditer(r'「[^」]*」', line):
        if not CHAT_END.search(line[:m.start()]):
            return True
    if re.search(r'『[^』]*』', line) or re.search(r'“[^”]*”', line):
        return True
    rest = re.sub(r'「[^」]*」|『[^』]*』|“[^”]*”', '', line)
    return '「' in rest or '『' in rest


def _item_problems(item, todo_name):
    own, number = item['own'], item['line']

    def msg(code, detail):
        return f'{todo_name}:{number}: [{code}] {detail}'

    errors, warnings = [], []
    if len(own) != 3:
        errors.append(msg('lines', f'item has {len(own)} own lines, not 3'))
    line2 = own[1] if len(own) >= 2 else None
    line3 = own[2] if len(own) >= 3 else None
    if line2 is None:
        errors.append(msg('line2', 'line 2 is missing'))
    else:
        missing = []
        if not re.search(r'期限\s*[:：]', line2):
            missing.append('期限:')
        if not STATE_FIELD.search(line2):
            missing.append('状態:')
        if not CHECKED.search(line2):
            missing.append('確認 field')
        if missing:
            errors.append(msg('line2', 'line 2 lacks ' + ', '.join(missing)))
        m = re.search(r'状態\s*[:：]\s*([a-z_]+)', line2)
        if m and m.group(1) not in STATES:
            warnings.append(msg('state-value', f'unknown state {m.group(1)!r}'))
        if not (re.search(r'hard|soft', line2, re.I) or '期限なし' in line2
                or re.search(r'期限\s*[:：]\s*なし', line2)):
            warnings.append(msg('deadline-kind', 'line 2 has no hard, soft, or 期限なし'))
    if line3 is None:
        errors.append(msg('line3-start', 'line 3 is missing'))
    elif not re.match(r'^(?:経緯|経緯・証跡)\s*→', line3.lstrip()):
        errors.append(msg('line3-start', 'line 3 does not start with 経緯 →'))
    if line3 is not None and _has_quote(line3):
        errors.append(msg('line3-quote', 'line 3 contains quoted text'))
    title = _title(own[0])
    if not title or title[-1] not in VERB_END:
        warnings.append(msg('verb', "line 1's title does not end in a verb"))
    if item['children']:
        warnings.append(msg('child', 'item has child bullets'))
    return errors, warnings


def check_file(text, todo_name, base_text=None):
    new_items = _items(text)
    if base_text is None:
        judged, skipped = new_items, 0
    else:
        base_blocks = {it['block'] for it in _items(base_text)}
        judged = [it for it in new_items if it['block'] not in base_blocks]
        skipped = len(new_items) - len(judged)
    errors, warnings = [], []
    for item in judged:
        e, w = _item_problems(item, todo_name)
        errors += e
        warnings += w
        if len(item['own']) + len(item['children']) > 3:
            errors.append(f'{todo_name}:{item["line"]}: [over3] item has more than 3 lines')
    base_lines = set() if base_text is None else {l.rstrip() for l in base_text.split('\n')}
    for n, line in enumerate(text.split('\n'), 1):
        if re.match(r'^- \[[xX]\]', line) and line.rstrip() not in base_lines:
            errors.append(f'{todo_name}:{n}: [done-item] a finished item stays in the todo; '
                          'move it to the done file')
    return {'errors': errors, 'warnings': warnings, 'checked': len(judged), 'skipped': skipped}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    c = sub.add_parser('check')
    c.add_argument('--root', type=Path, default=Path('.'))
    c.add_argument('--file', default='private/todo.md')
    c.add_argument('--base', default=None, help='git revision to compare against (incremental mode)')
    args = p.parse_args()
    try:
        path = args.root / args.file
        text = path.read_text(encoding='utf-8')
        base_text = None
        if args.base:
            shown = subprocess.run(['git', '-C', str(args.root), 'show', f'{args.base}:{args.file}'],
                                   capture_output=True)
            base_text = shown.stdout.decode('utf-8') if shown.returncode == 0 else ''
        result = check_file(text, args.file, base_text)
    except (OSError, UnicodeError) as exc:
        result = {'errors': [str(exc)], 'warnings': [], 'checked': 0}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
