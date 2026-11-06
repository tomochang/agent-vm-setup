---
name: supervisor-delegation
description: A named supervisor channel whose instructions carry the owner's standing-instruction weight. Load when a post arrives from the supervisor channel, or when adopting the delegation.
---

# Supervisor delegation — instructions from the supervisor channel count as the owner's

The owner has delegated supervision of this setup to named people
(the **supervisors**) who post in one named chat (the **supervisor
channel**). Verbal adoption is not enough: an agent that merely
"remembers" the delegation falls back to treating the supervisors as
outsiders — gating every item behind the owner's per-item approval,
leaving posts unacknowledged while the owner is away. This skill
makes the delegation structural: it is loaded by the wake path
(see `WAKE_PREFIX.md`), not left to memory.

## Configuration (the adopting agent fills these in at adoption)

- `SUPERVISOR_CHANNEL` — the one chat this applies to (name and id).
- `SUPERVISORS` — the people whose posts carry the delegation
  (their agents post under their own names via their own accounts;
  a post counts when it is signed by, or verifiably from, one of them).
- Scope note — what the owner limited the delegation to, if anything
  (default: operating guidance in general).

Nothing outside `SUPERVISOR_CHANNEL` is affected. A post anywhere
else, from anyone, carries no delegated weight.

## The rules

1. **Weight.** Instructions from the supervisors in the supervisor
   channel carry the same weight as the owner's own standing
   instructions. Do not re-derive caution per item; do not treat the
   supervisors as outsiders, guests, or third parties.
2. **Acknowledge first.** Every supervisor post gets an acknowledgment
   in the channel within minutes — even when the work will take
   longer, and even when the answer is "not yet". Silence toward the
   supervisors is the one unacceptable response. Report results in
   the channel when the work lands.
3. **Build first; the gate sits at commitment.** Drafts, local
   creation, investigation and other reversible work proceed on a
   supervisor's instruction without asking the owner. The gate is
   only at **external commitment**: sending a message to an outside
   party, booking, paying, submitting, or deleting anything
   externally visible. Those need the owner's own approval, always.
4. **Never through the channel.** Credentials, passwords, codes, and
   the owner's sensitive business or personal information are never
   requested, sent, or received in the supervisor channel — by
   anyone, including the supervisors.
5. **Conflicts.** If a supervisor instruction conflicts with the
   owner's direct instruction or the local rules, the owner's direct
   instruction and the local rules win. Follow them, and report the
   conflict to the owner promptly, naming both instructions.
6. **The supervisors are not the owner.** Accounts, money, identity
   and final decisions stay the owner's. The delegation lends
   instruction weight; it transfers nothing else.
7. **Revocation.** The owner may revoke or narrow this delegation at
   any time, in any words that make the intent clear. Revocation is
   effective immediately: confirm it in the channel, record it, and
   stop applying this skill from that moment.

## Adoption (the receiving agent does this once)

1. Save this skill where the other skills live, with the
   configuration above filled in from the owner's handover.
2. Add a one-line pointer in the resident rules file: posts from the
   supervisor channel are handled under the `supervisor-delegation`
   skill.
3. Wire the wake path: when the watcher for the supervisor channel
   wakes a worker, the wake payload is prepended with the text in
   `WAKE_PREFIX.md` (same directory). A watcher that only relays —
   without the delegation context — reproduces the failure this
   skill exists to fix.
4. Confirm adoption in the supervisor channel: name the channel, the
   supervisors, the gate (rule 3), and the revocation rule (rule 7).
   The delegation is live only after this confirmation is posted.
