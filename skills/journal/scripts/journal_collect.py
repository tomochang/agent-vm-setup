#!/usr/bin/env python3
"""Collect one journal day from Calendar, Gmail, GitHub, Beeper and Todo into JSON.

Read-only. The LLM reads this output instead of calling each tool itself.
Usage: python3 skills/journal/scripts/journal_collect.py --day 2026-10-13
"""
import argparse
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.parse
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
LATE_NIGHT_HOURS = 4  # 深夜は前夜の続き
MAX_AREAS = 8
MAX_MESSAGE_PAGES = 30  # Beeper APIは1ページ20件


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


beeper = _load('beeper_sync', ROOT / 'scripts/beeper_sync.py')
journal_tool = _load('journal_tool', Path(__file__).with_name('journal_tool.py'))


def window(day, timezone):
    start = dt.datetime.combine(dt.date.fromisoformat(day), dt.time(), ZoneInfo(timezone))
    return start, start + dt.timedelta(days=1, hours=LATE_NIGHT_HOURS)


def _ts(value):
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00'))


# ── shaping (pure) ──────────────────────────────────────────

def shape_calendar(events):
    out = []
    for e in events:
        if e.get('status') == 'cancelled':
            continue
        start, end = e.get('start') or {}, e.get('end') or {}
        item = {'id': e.get('id'), 'summary': e.get('summary', ''),
                'start': start.get('dateTime') or start.get('date'),
                'end': end.get('dateTime') or end.get('date'),
                'all_day': 'date' in start and 'dateTime' not in start,
                'tentative': '[仮]' in (e.get('summary') or '')}
        if e.get('location'):
            item['location'] = e['location']
        out.append(item)
    return out


def _labels(value):
    if isinstance(value, str):
        return re.findall(r'[A-Z_0-9]+', value)
    return list(value or [])


def _excluded(sender, domains):
    found = re.findall(r'[^\s<>@]+@([a-zA-Z0-9.-]+)', sender or '')
    if not found:
        return False
    domain = found[-1].lower().rstrip('.')
    return any(domain == d or domain.endswith('.' + d) for d in domains)


def shape_gmail(messages, exclude_domains):
    items, promotions, staging = [], 0, 0
    for m in messages:
        if _excluded(m.get('from'), exclude_domains):
            staging += 1
            continue
        labels = _labels(m.get('labels'))
        if 'CATEGORY_PROMOTIONS' in labels:
            promotions += 1
            continue
        items.append({'id': m.get('id'), 'thread': m.get('threadId'), 'date': m.get('date'),
                      'from': m.get('from'), 'subject': m.get('subject'),
                      'direction': 'sent' if 'SENT' in labels else 'received'})
    return {'items': items, 'promotions_omitted': promotions, 'excluded_staging': staging}


def parse_git_log(raw):
    commits = []
    for block in raw.split('\x1e'):
        if not block.strip():
            continue
        head, _, rest = block.partition('\n')
        sha, at, subject = (head.split('\x1f') + ['', '', ''])[:3]
        files = [line for line in rest.splitlines() if line.strip()]
        areas = list(dict.fromkeys('/'.join(f.split('/')[:2]) for f in files))
        commits.append({'hash': sha[:10], 'at': at, 'subject': subject,
                        'areas': areas[:MAX_AREAS], 'files_total': len(files)})
    return commits


def shape_github_events(events, start, end, this_repo):
    out = []
    for e in events:
        repo = (e.get('repo') or {}).get('name')
        at = e.get('created_at')
        if repo == this_repo or not at or not (start <= _ts(at) < end):
            continue
        commits = [(x.get('message') or '').split('\n', 1)[0] for x in (e.get('payload') or {}).get('commits') or []]
        out.append({'repo': repo, 'type': e.get('type'), 'at': at, 'commits': commits})
    return out


def select_chats(chats, start, end):
    """期間内に1通でもメッセージがあるチャットを全部残す（2026-10-27 本人: Beeper は全部読む。グループ・WhatsApp・アーカイブも）。"""
    out = []
    for chat, messages in chats:
        visible = sorted((m for m in messages
                          if m.get('type') != 'REACTION' and not m.get('isHidden') and m.get('timestamp')
                          and start <= _ts(m['timestamp']) < end), key=lambda m: m['timestamp'])
        if not visible:
            continue
        out.append({'account': chat.get('accountID'), 'title': chat.get('title', ''),
                    'type': chat.get('type', ''), 'participants': beeper.participant_total(chat), 'messages': [
            {'at': _ts(m['timestamp']).astimezone(start.tzinfo).isoformat(),
             'from': 'operator' if m.get('isSender') else (m.get('senderName') or '相手'),
             'text': beeper.clean_text(m.get('text') or '') or '(テキストなし)'} for m in visible]})
    return out


GIT_LOG_ARGS = ['--date=iso-strict', '--format=%x1e%H%x1f%ad%x1f%s', '--name-only']


def local_repo_commits(roots, start, end):
    """roots 直下の git リポ（remote の無い ~/factory/* 等）から期間内の commit を集める。"""
    out = []
    for root in roots:
        base = Path(os.path.expanduser(root))
        if not base.is_dir():
            continue
        for d in sorted(p for p in base.iterdir() if (p / '.git').exists()):
            raw = subprocess.run(['git', '-c', 'core.quotePath=false', 'log', '--all', f'--since={start.isoformat()}',
                                  f'--until={end.isoformat()}', *GIT_LOG_ARGS],
                                 cwd=d, capture_output=True, text=True).stdout
            commits = parse_git_log(raw)
            if commits:
                out.append({'repo': str(d), 'commits': commits})
    return out


def _hm(value):
    return _ts(value).strftime('%H:%M') if 'T' in value else value[-5:]


def _topic(commit):
    head, sep, _ = commit['subject'].partition(':')
    if sep and len(head) <= 40:
        return head
    return (commit.get('areas') or ['(その他)'])[0]


def _commit_lines(commits):
    groups = {}
    for cm in sorted(commits, key=lambda x: x['at']):
        groups.setdefault(_topic(cm), []).append(cm)
    lines = []
    for topic, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        subjects = ' / '.join(x['subject'] for x in items[-3:])
        lines.append(f'  - {topic} ×{len(items)}（{_hm(items[0]["at"])}〜{_hm(items[-1]["at"])}）: {subjects}')
    return lines


def digest(result):
    """集めた項目を情報源ごとに1つも落とさず並べる。日記の最初の提示はこれをそのまま使う（LLMが選ばない）。"""
    s = result['sources']
    lines = [f'# {result["journal_date"]} の記録（全件）']

    def section(name, key):
        src = s.get(key, {})
        if src.get('status') != 'ok':
            lines.append(f'{name}: {src.get("status", "missing")} {src.get("error", "")}'.rstrip())
            return None
        lines.append(f'{name}:')
        return src['data']

    cal = section('Calendar', 'calendar')
    for e in cal or []:
        lines.append(f'  - {_hm(e["start"])}〜{_hm(e["end"])} {e["summary"]}')
    gm = section('Gmail', 'gmail')
    if gm is not None:
        for m in sorted(gm['items'], key=lambda x: x['date']):
            arrow = '送信' if m['direction'] == 'sent' else '受信'
            lines.append(f'  - {m["date"][-5:]} {arrow} {m["from"][:40]} | {m["subject"]}')
        lines.append(f'  - (プロモーション {gm.get("promotions_omitted", 0)} 件は省略)')
    gh = section('GitHub', 'github')
    if gh is not None:
        lines.append(f' records {len(gh["commits"])} commit:')
        lines += _commit_lines(gh['commits'])
        for r in gh.get('local_repos', []):
            lines.append(f' {r["repo"]} {len(r["commits"])} commit:')
            lines += _commit_lines(r['commits'])
        for e in gh.get('other_repos', []):
            lines.append(f'  - {e["repo"]} {e["type"]} {_hm(e["at"])}: {" / ".join(e["commits"])}')
    bp = section('Beeper', 'beeper')
    if bp is not None:
        for ch in sorted(bp['chats'], key=lambda x: x['messages'][-1]['at']):
            mine = sum(m['from'] == 'operator' for m in ch['messages'])
            kind = f'グループ{ch.get("participants") or ""}人' if ch.get('type') == 'group' else '1対1'
            lines.append(f'  - {ch["title"]}（{ch["account"].split(".")[0]}・{kind}）{len(ch["messages"])}通（自分{mine}）'
                         f' 最終{_hm(ch["messages"][-1]["at"])}')
        if bp.get('may_be_truncated'):
            lines.append(f'  - 取り切れていない可能性: {", ".join(bp["may_be_truncated"])}')
    td = section('Todo（対象日まで）', 'todo')
    for t in td or []:
        lines.append(f'  - {t["label"]} {t["title"]}')
    return '\n'.join(lines)


def collect(day, timezone, fetchers):
    start, end = window(day, timezone)
    sources = {}
    for name in ('calendar', 'gmail', 'github', 'beeper', 'todo'):
        try:
            data = fetchers[name](day) if name == 'todo' else fetchers[name](start, end)
            sources[name] = {'status': 'unavailable'} if data is None else {'status': 'ok', 'data': data}
        except Exception as exc:  # noqa: BLE001 — 1つの失敗で全体を止めない
            sources[name] = {'status': 'error', 'error': f'{type(exc).__name__}: {exc}'[:300]}
    return {'journal_date': day, 'timezone': timezone,
            'window': {'start': start.isoformat(), 'end': end.isoformat()}, 'sources': sources}


# ── fetchers (I/O) ──────────────────────────────────────────

def fetch_window_messages(get, chat_id, start, max_pages=MAX_MESSAGE_PAGES):
    """期間の開始より古いメッセージに届くまでページを遡る。取り切れたかも返す。"""
    path = f"/v1/chats/{urllib.parse.quote(chat_id, safe='')}/messages"
    items, params = [], {'limit': 20}
    for _ in range(max_pages):
        page = get(path, params)
        items += page.get('items', [])
        if not page.get('hasMore') or any(_ts(m['timestamp']) < start for m in page.get('items', [])):
            return items, True
        if not page.get('oldestCursor'):
            return items, False
        params = {'limit': 20, 'cursor': page['oldestCursor'], 'direction': 'before'}
    return items, False


def _run(cmd, cwd=None):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=cwd)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[:200])
    return r.stdout


def _gog():
    return os.environ.get('GOG_PATH') or shutil.which('gog') or 'gog'


def fetch_calendar(account):
    def f(start, end):
        raw = _run([_gog(), 'calendar', 'events', 'primary', '--from', start.isoformat(), '--to', end.isoformat(),
                    '--all-pages', '--max', '250', '--json', '--account', account])
        return shape_calendar(json.loads(raw).get('events') or [])
    return f


def fetch_gmail(account, exclude_domains):
    def f(start, end):
        query = f'after:{int(start.timestamp())} before:{int(end.timestamp())}'
        raw = _run([_gog(), 'gmail', 'messages', 'search', query, '--max', '500', '--json', '--account', account])
        return {'account': account, **shape_gmail(json.loads(raw).get('messages') or [], exclude_domains)}
    return f


def fetch_github(repo_root, this_repo, user, local_roots=()):
    def f(start, end):
        raw = _run(['git', '-c', 'core.quotePath=false', 'log', '--all', f'--since={start.isoformat()}', f'--until={end.isoformat()}',
                    *GIT_LOG_ARGS], cwd=repo_root)
        events = json.loads(_run(['gh', 'api', f'users/{user}/events?per_page=100']))
        return {'commits': parse_git_log(raw), 'other_repos': shape_github_events(events, start, end, this_repo),
                'local_repos': local_repo_commits(local_roots, start, end)}
    return f


def fetch_beeper():
    def f(start, end):
        if not beeper.TOKEN_FILE.exists():
            return None
        try:
            accounts = beeper.api_get('/v1/accounts', {})
        except OSError:
            return None  # Beeper Desktop未起動・Mac外
        accounts = accounts.get('items', []) if isinstance(accounts, dict) else accounts
        if not accounts:
            raise RuntimeError('Beeper returned no accounts')  # 空の日に見せない（digest に error として出る）
        pairs, truncated = [], []
        for a in accounts:
            acct = a.get('accountID') or a.get('id')
            for chat in beeper.fetch_chats(acct):
                if not chat.get('lastActivity') or _ts(chat['lastActivity']) < start:
                    continue
                chat = {**chat, 'accountID': acct}
                msgs, complete = fetch_window_messages(beeper.api_get, chat['id'], start)
                if not complete:
                    truncated.append(chat.get('title', ''))
                pairs.append((chat, msgs))
        return {'chats': select_chats(pairs, start, end), 'may_be_truncated': truncated}
    return f


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--day', required=True)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--digest', action='store_true', help='全件の一覧（日記の最初の提示用）を出す')
    args = parser.parse_args(argv)
    config = json.loads((args.root / 'private/journal/config.json').read_text())
    gmail_cfg = config['sources']['gmail']
    local_roots = config['sources'].get('github', {}).get('local_repo_roots', [])
    fetchers = {
        'calendar': fetch_calendar(gmail_cfg['account']),
        'gmail': fetch_gmail(gmail_cfg['account'], gmail_cfg['exclude_sender_domains']),
        'github': fetch_github(args.root, config['repository'], config['repository'].split('/')[0], local_roots),
        'beeper': fetch_beeper(),
        'todo': lambda day: journal_tool.overdue_schedule(
            (args.root / 'private/todo.md').read_text(), dt.date.fromisoformat(day)),
    }
    result = collect(args.day, config['timezone'], fetchers)
    print(digest(result) if args.digest else json.dumps(result, ensure_ascii=False, separators=(',', ':')))
    return 0 if all(s['status'] == 'ok' for s in result['sources'].values()) else 3


if __name__ == '__main__':
    sys.exit(main())
