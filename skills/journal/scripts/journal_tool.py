#!/usr/bin/env python3
"""Journal integrity/status utility. Python 3.9+; no network, credentials or LLM."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import unquote, urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
REQUIRED = {'schema_version', 'id', 'type', 'journal_date', 'recorded_on', 'timezone', 'status', 'title'}
STAGES = {'draft', 'confirmed'}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def metadata(text):
    if not text.startswith('---\n'):
        raise ValueError('missing YAML frontmatter')
    head, sep, body = text[4:].partition('\n---\n')
    if not sep:
        raise ValueError('unclosed YAML frontmatter')
    result = {}
    for line in head.splitlines():
        key, colon, value = line.partition(':')
        if not colon or key in result:
            raise ValueError('invalid or duplicate metadata key')
        result[key] = json.loads(value.strip())
    if not REQUIRED.issubset(result):
        raise ValueError('missing required metadata')
    if result['schema_version'] != 1 or result['type'] != 'journal-entry':
        raise ValueError('unsupported entry schema')
    if result['status'] not in STAGES:
        raise ValueError('invalid entry status')
    day = dt.date.fromisoformat(result['journal_date']).isoformat()
    dt.date.fromisoformat(result['recorded_on'])
    ZoneInfo(result['timezone'])
    if result['id'] != 'J-' + day or not result['title'] or not body.strip():
        raise ValueError('invalid identity, title or empty body')
    return result

def journal_day(value, timezone='Asia/Tokyo', rollover_hour=12):
    now = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if now.tzinfo is None:
        raise ValueError('timestamp must include timezone')
    local = now.astimezone(ZoneInfo(timezone))
    return (local.date() - dt.timedelta(days=int(local.hour < rollover_hour))).isoformat()

def duplicate_turn_labels(text):
    labels = re.findall(r'^### ([TUA]\d+)(?:\s+—[^\n]*)?$', text, flags=re.M)
    seen, duplicates = set(), []
    for label in labels:
        if label in seen and label not in duplicates:
            duplicates.append(label)
        seen.add(label)
    return duplicates

def repeated_long_blocks(text, min_chars=80):
    # Entry body only. Exact long-block duplication is suspicious; semantic
    # duplication remains a human quality-gate concern in SKILL.md.
    if text.startswith('---\n'):
        _, sep, text = text[4:].partition('\n---\n')
        if not sep:
            return []
    text = re.sub(r'```.*?```', '', text, flags=re.S)
    seen, duplicates = {}, []
    for raw in re.split(r'\n\s*\n', text):
        block = raw.strip()
        if not block or block.startswith(('#', '-', '* ', '[', '<a ', '---')):
            continue
        normalized = re.sub(r'\s+', ' ', block)
        if len(normalized) < min_chars:
            continue
        if normalized in seen and normalized not in duplicates:
            duplicates.append(normalized)
        seen[normalized] = True
    return duplicates

def overdue_schedule(text, today, section='## 今後の確定予定と残作業'):
    """Rows of the confirmed-schedule table whose end date is on or before today (open-ended rows never expire)."""
    try:
        body = text.split(section, 1)[1].split('\n## ', 1)[0]
    except IndexError:
        return []
    year = today.year
    m = re.search(r'(\d{4})年', body)
    if m: year = int(m.group(1))
    rows = []
    for line in body.splitlines():
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) < 2 or not re.match(r'\d{1,2}/\d{1,2}', cells[0]): continue
        if '未定' in cells[0]: continue
        dates = re.findall(r'(\d{1,2})/(\d{1,2})', cells[0])
        end = dt.date(year, int(dates[-1][0]), int(dates[-1][1]))
        if end <= today:
            rows.append({'label': cells[0], 'title': cells[1], 'end': end.isoformat()})
    return rows

def decide(confirmed, run, sources_complete, busy):
    if confirmed:
        return 'done'
    if run.get('notification_status') in {'claimed', 'sent', 'delivery_uncertain', 'manual_session'} or run.get('stage') == 'awaiting_user':
        return 'awaiting_user'
    if not sources_complete:
        return 'blocked_sources'
    if busy:
        return 'defer'
    return 'prompt'

def validate(root):
    root = Path(root).resolve()
    base = root / 'private/journal'
    errors, warnings = [], []
    try:
        protected = json.loads((base / 'protected.json').read_text())['files']
    except (OSError, ValueError, KeyError) as exc:
        return {'errors': ['protected manifest: ' + str(exc)], 'warnings': []}
    protected_manifests = [(base / 'protected.json', protected)]
    for demo_manifest in (base / 'demos').glob('*/protected.json'):
        try:
            protected_manifests.append((demo_manifest, json.loads(demo_manifest.read_text())['files']))
        except (OSError, ValueError, KeyError) as exc:
            errors.append('demo protected manifest: ' + str(demo_manifest) + ': ' + str(exc))
    for manifest_path, files in protected_manifests:
        for rel, expected in files.items():
            path = (root / rel).resolve()
            if not path.is_relative_to(root):
                errors.append('protected path escapes root: ' + rel)
            elif not path.is_file():
                errors.append('protected missing: ' + rel)
            elif digest(path.read_bytes()) != expected:
                errors.append('protected content changed: ' + rel + ' via ' + str(manifest_path))
    for path in (base / 'entries').glob('*/*/*.md'):
        try:
            info = metadata(path.read_text())
            if path.stem != info['journal_date'] or path.parent.name != info['journal_date'][5:7] or path.parent.parent.name != info['journal_date'][:4]:
                errors.append('entry date/path mismatch: ' + str(path))
            if info['status'] == 'confirmed' and path.relative_to(root).as_posix() not in protected:
                errors.append('confirmed entry has no protection: ' + str(path))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append('entry metadata: ' + str(path) + ': ' + str(exc))
    for path in base.rglob('*.md'):
        text = re.sub(r'```.*?```', '', path.read_text(), flags=re.S)
        for link in re.findall(r'\]\(([^)]+)\)', text):
            u = urlsplit(link)
            if u.scheme or u.netloc:
                continue
            target = (path.parent / unquote(u.path)).resolve() if u.path else path
            if not target.is_relative_to(root):
                errors.append('link escapes root: ' + link)
                continue
            # A partial checkout can omit other systems; validate all journal-local targets.
            if not target.is_file():
                if target.is_relative_to(base):
                    errors.append('missing link: ' + link + ' in ' + str(path))
                continue
            if u.fragment and target.suffix == '.md':
                target_text = target.read_text()
                anchors = re.findall(r'<a\s+(?:name|id)="([^"]+)"', target_text)
                if unquote(u.fragment) not in anchors:
                    errors.append('missing explicit anchor: ' + link)
    statement_paths = list((base / 'sources').glob('*/*/*/statements.md'))
    statement_paths += list((base / 'demos').glob('*/statements.md'))
    for statements in statement_paths:
        try:
            duplicates = duplicate_turn_labels(statements.read_text())
            for label in duplicates:
                errors.append('duplicate journal turn label ' + label + ': ' + str(statements))
        except OSError as exc:
            errors.append('statements read: ' + str(statements) + ': ' + str(exc))
    entry_paths = list((base / 'entries').glob('*/*/*.md'))
    entry_paths += list((base / 'demos').glob('*/entry.md'))
    for entry in entry_paths:
        try:
            for block in repeated_long_blocks(entry.read_text()):
                errors.append('duplicate long entry block: ' + str(entry) + ': ' + block[:120])
        except OSError as exc:
            errors.append('entry duplicate scan: ' + str(entry) + ': ' + str(exc))
    for manifest in (base / 'sources').glob('*/*/*/assets.json'):
        try:
            for asset in json.loads(manifest.read_text())['assets']:
                name = asset['filename']
                if Path(name).name != name:
                    raise ValueError('unsafe asset filename')
                path = manifest.parent / name
                if path.exists() and digest(path.read_bytes()) != asset['sha256']:
                    errors.append('asset hash mismatch: ' + str(path))
                if asset['repository_status'] == 'stored' and not path.is_file():
                    errors.append('stored asset missing: ' + str(path))
                elif asset['repository_status'] != 'stored':
                    warnings.append('asset pending repository verification: ' + str(path))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append('asset manifest: ' + str(exc))
    return {'errors': errors, 'warnings': warnings}

def status(root, day):
    day = dt.date.fromisoformat(day).isoformat()
    base = Path(root) / 'private/journal'
    entry = base / 'entries' / day[:4] / day[5:7] / (day + '.md')
    runfile = base / 'runs' / (day + '.json')
    run = json.loads(runfile.read_text()) if runfile.exists() else {}
    confirmed = entry.exists() and metadata(entry.read_text())['status'] == 'confirmed'
    if confirmed:
        protected = json.loads((base / 'protected.json').read_text())['files']
        rel = entry.relative_to(Path(root)).as_posix()
        if protected.get(rel) != digest(entry.read_bytes()):
            raise ValueError('confirmed entry failed integrity check')
    return {'journal_date': day, 'confirmed': confirmed, 'run': run,
            'next': decide(confirmed, run, False, False),
            'note': 'Source access and current calendar availability must be checked by the connected agent.'}

def worksheet_gate(root, day):
    """Block completion of CoachEd homework until the dated live readback is recorded."""
    day = dt.date.fromisoformat(day).isoformat()
    if not ('2026-10-01' <= day <= '2026-10-07'):
        return {'day': day, 'applicable': False, 'errors': []}
    root = Path(root).resolve()
    entry = root / 'private/journal/entries' / day[:4] / day[5:7] / (day + '.md')
    ledger = root / 'private/journal/worksheet-sync-tests' / ('journal_' + day.replace('-', '') + '.json')
    errors = []
    if not entry.is_file() or metadata(entry.read_text())['status'] != 'confirmed':
        return {'day': day, 'applicable': True, 'errors': ['confirmed journal entry missing']}
    if not ledger.is_file():
        return {'day': day, 'applicable': True, 'errors': ['worksheet readback record missing']}
    record = json.loads(ledger.read_text())
    if record.get('journal_date') != day or record.get('state') != 'synced':
        errors.append('worksheet is not synced for this day')
    if record.get('entry_sha256') != digest(entry.read_bytes()):
        errors.append('worksheet record does not match current journal entry')
    if not all(record.get('payload', {}).get(key) for key in ('title', 'scene', 'body', 'emotion', 'without_gain')):
        errors.append('worksheet field missing')
    readback = record.get('readback') or {}
    if not readback.get('exact_title_and_four_fields') or not readback.get('revision_id') or not readback.get('checked_at'):
        errors.append('live worksheet readback not recorded')
    return {'day': day, 'applicable': True, 'errors': errors}

def restore_assets(root, source_dir):
    root, source_dir = Path(root).resolve(), Path(source_dir).resolve()
    copied = []
    for manifest in (root / 'private/journal/sources').glob('*/*/*/assets.json'):
        for asset in json.loads(manifest.read_text())['assets']:
            if Path(asset['filename']).name != asset['filename']:
                raise ValueError('unsafe asset filename')
            dst = manifest.parent / asset['filename']
            src = source_dir / dst.relative_to(root)
            if not src.resolve().is_relative_to(source_dir) or not dst.resolve().is_relative_to(root):
                raise ValueError('asset path escapes allowed directory')
            content = src.read_bytes()
            if digest(content) != asset['sha256']:
                raise ValueError('source asset hash mismatch: ' + str(src))
            if dst.exists():
                if digest(dst.read_bytes()) != asset['sha256']:
                    raise ValueError('refusing to overwrite different asset: ' + str(dst))
                continue
            with dst.open('xb') as out:
                out.write(content)
            copied.append(dst.relative_to(root).as_posix())
    return {'copied': copied, 'repository_upload': 'not_performed'}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('validate')
    p = sub.add_parser('todo-overdue'); p.add_argument('--day', required=True)
    p = sub.add_parser('status'); group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--date'); group.add_argument('--at')
    p = sub.add_parser('worksheet-gate'); p.add_argument('--date', required=True)
    p = sub.add_parser('restore-assets'); p.add_argument('--source-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'validate': result = validate(args.root)
        elif args.command == 'todo-overdue':
            result = {'day': args.day, 'overdue': overdue_schedule((args.root / 'private/todo.md').read_text(), dt.date.fromisoformat(args.day))}
        elif args.command == 'status':
            config = json.loads((args.root / 'private/journal/config.json').read_text())
            day = args.date or journal_day(args.at, config['timezone'], config['daily']['journal_day_rollover_hour'])
            result = status(args.root, day)
        elif args.command == 'worksheet-gate': result = worksheet_gate(args.root, args.date)
        else: result = restore_assets(args.root, args.source_dir)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False)); return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(bool(result.get('errors')))

if __name__ == '__main__':
    sys.exit(main())
