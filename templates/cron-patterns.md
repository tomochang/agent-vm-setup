# Scheduled-job patterns

Three small jobs keep the whole system honest. Adapt cadence freely;
keep the "silent when healthy" property — a job that chats when
nothing is wrong trains the human to ignore it.

## 1. Records auto-pull (~30 min)

`git fetch origin` as its own step, then
`git pull --no-rebase --no-edit` (never `--autostash`).
Silent unless the tree is dirty or a pull conflicts — those two mean
a human-grade record problem, not noise.

## 2. Health check (30 min)

ping (healthchecks) → bootstrap-check → if failing: vm-bootstrap once
→ re-check → if still failing: surface one short message naming the
failing lines. Repeats every run until fixed, by design. See
`health/` for the check/bootstrap templates and SETUP.md Phase 5.

## 3. Failure-ledger check (30 min)

Run the ledger's `check`; silent when clean. Notify the human about
any signature with 2+ occurrences and no mechanism — that is the
queue of things to systematize next.
