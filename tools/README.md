# Tools — operator utilities for the agent-VM setup

Small, mostly-stdlib tools. Each lives in its own directory so it can
be copied alone into the records repo's tooling. Path defaults assume
the layout in `SETUP.md` (workspace root + records checkout); where a
tool hardcodes a source-system path, the override is listed.

| Tool | What it does | Configure |
|---|---|---|
| `action-journal/` | Intent/done/reconcile journal for external actions (booking, send, land). Callers pass `--journal`; the default is `actions.jsonl` next to the script. | `ACTION_JOURNAL_PATH` |
| `calendar-block/` | Show a calendar event's whole block, including linked movement events, before/after a time change. | Calendar connector |
| `channel-watch/` | FAIL when a counterpart channel with recent posts has no enabled watcher. The shipped registry is empty on purpose — add your channels. | `BEEPER_API_DIR` |
| `doc-coverage/` | Every tool script must be named in a landed records doc. | `RECORDS_DIR`, `AGENT_TOOL_DIRS` |
| `env-heal/` | Heal a stuck VM env (apt lock, missing runtime) for the bootstrap check. | `BOOTSTRAP_CHECK` |
| `foreman-handoff/` | Instruction-template check + cap-floor check + the task-file template for worker handoffs. | — |
| `gh-fetch/` | Read a file from the records repo via the platform GitHub tool. | `RECORDS_OWNER`, `RECORDS_REPO` (or argv) |
| `improvement-scout/` | Collect improvement signals (incl. stale todo rows) for the improvement loop. | `RECORDS_DIR`, `FAILURE_LEDGER`, `HANDOFF_DIR`, `ITEMS_DIR`, `TODO_FILE` |
| `mechanism-coverage/` | Every repo/research mechanism must be named in a landed records doc. | `AGENT_VM_ROOT`, `RECORDS_DIR` |
| `receipt-lib/` | Receipt classification library (company-card statement matching). Used by the `sride-receipts` / `uber-receipts` skills. | — |
| `sot-read/` | Read the records todo file / log efficiently. | `RECORDS_DIR`, `TODO_FILE`, `TODO_LOG_FILE` |
| `source-mirror/` | Byte-compare VM tool copies against the records mirror. | `--mirror-root`, `--workspace` |
| `spend-governor/` | Meter CLI spend (weighted units) against a daily cap. Copy `spend-governor.json.example` to `spend-governor.json` and re-derive the cap from your own rolling average; do not keep the example numbers. Ships with its `cache_caller_report.py` dependency; `usage_report` is resolved from `../usage-report/`. | `--config`, `--projects` |
| `usage-report/` | Aggregate token usage from CLI session logs. | `--projects`, `--codex` |
| `watchers/` | `chat-watch.sh.template`: poll one Beeper chat and wake the agent on a counterpart post. Copy per chat and set `WATCH_CHAT_ID`, `WATCH_STATE_FILE`, `OPERATOR_SENDER_PREFIX`, `BEEPER_API_DIR`. The worker that receives the wake payload relays posts verbatim — no summary or interpretation on the relay path. | See `watchers/README.md` |

Already in this repo (not duplicated here): `beeper/` (launch, OAuth,
liveness, API, CDP driver), `health/` (failure ledger, health-loop
templates), `todo/` (format, checker, job patterns), `workflows/`
(watchers, gates, handoff, improvement loop).
