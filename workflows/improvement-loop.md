# The improvement loop — small trials, run on a schedule

Autonomy that only reacts is half the job. A periodic loop
(every ~4 hours here) looks for improvements and *finishes* a few:

1. **Collect signals.** Stale todo items, repeated failures from the
   ledger, unwatched channels, drift between local tools and the
   records repo, upcoming deadlines without preparation.
2. **Pick at most 2.** Low-risk, reversible, and inside the recorded
   authority. Anything touching money, privacy, or destructive
   operations is prepared for the human instead of executed.
3. **Execute end-to-end.** Research, change, verification, and the
   records landing through the gates — the loop does not produce
   proposals that wait for a second pass; it produces finished,
   checked changes, or a prepared decision with a recommendation.
4. **Report only what was done.** A loop run that changed nothing is
   silent. A report names the change and its verification, briefly.

## Principles that keep it healthy

- **Many light tries over few big programs.** Small, simple, fast
  trials; action volume and learning speed beat polish. A trial that
  fails cheaply and gets recorded is worth more than a plan.
- **Best practice first.** Before designing anything, look at how
  practitioners actually do it and what the evidence shows; design
  from inference only where evidence cannot be collected — and mark
  the gap instead of filling it with a guess.
- **Infrastructure is a means.** The loop's objective is the human's
  outcomes (capital, relationships, experiences, lower cost), not a
  tidier system for its own sake. When both kinds of candidate exist,
  at least one slot goes to a life-facing one.
- **Failures feed the ledger.** Anything the loop breaks or finds
  broken is logged with a signature; a repeat makes a mechanism
  mandatory.
