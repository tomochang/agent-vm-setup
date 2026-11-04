"""Offline journal source gate; profile must come from the active provider session."""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]

def require_account(config, profile):
    policy = config['sources']['gmail']
    if not isinstance(profile, dict):
        raise ValueError('journal Gmail profile must be a provider profile object')
    actual = profile.get('email') or profile.get('emailAddress')
    if not isinstance(actual, str) or actual.strip().lower() != policy['account']:
        raise ValueError('journal Gmail account is missing or does not match the allowed account')
    return policy

def filter_messages(config, profile, messages):
    policy = require_account(config, profile)
    kept = []
    for message in messages:
        sender = message.get('from_') or message.get('from')
        # Connector From may be "Display Name address@domain" without brackets.
        domains = re.findall(r'[^\s<>@]+@([a-zA-Z0-9.-]+)', sender or '')
        if len(domains) != 1:
            raise ValueError('journal Gmail message requires one verified From address')
        domain = domains[0].lower().rstrip('.')
        if any(domain == excluded or domain.endswith('.' + excluded)
               for excluded in policy['exclude_sender_domains']):
            continue
        kept.append(message)
    return kept

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'private/journal/config.json')
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--messages', type=Path)
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text())
        profile = json.loads(args.profile.read_text())
        require_account(config, profile)
        result = (filter_messages(config, profile, json.loads(args.messages.read_text()))
                  if args.messages else {'account_verified': True})
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, str(exc) + '\n')
    print(json.dumps(result, ensure_ascii=False))

if __name__ == '__main__':
    main()
