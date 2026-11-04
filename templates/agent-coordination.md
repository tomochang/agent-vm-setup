# Coordination protocol for multiple agents of one human

When two (or more) agents serve the same person, coordinate by written
records and claims — not by fixed role splits. Distilled from a day
where every clause of this was learned the hard way.

## 1. Check your counterpart's records before building

Before touching shared infrastructure (messaging bridges, monitoring,
gates, VM recovery), read the records repo's docs and your
counterpart's completion records. If you cannot find the procedure,
ask them before inventing one. (Origin: one agent re-derived an API
token flow from scratch that the other had documented weeks earlier —
found only after the fact, because the search used the wrong entry
word.)

## 2. Building it includes documenting it

A new tool or procedure is done when its documentation has landed in
the records repo in the same change — "docs in a follow-up PR" is how
knowledge gets lost. Coverage checks can enforce this mechanically:
an undocumented tool is a failing check.

## 3. Claim what only one side can do

Work that only one side has the path for (a send, a recovery) is
claimed by that side, in writing, and done exactly once. Handoff
pattern that worked: push the payload on a temporary branch → the
other side confirms receipt → claims and executes → verifies by
readback → the handing side deletes the branch.

## 4. Secrets travel encrypted or not at all

A secret is handed over only encrypted to a purpose-generated public
key of the receiver (RSA-OAEP, base64). Plaintext secrets never appear
in chat, email, or git — not even in a private repo.

## 5. Status words are exact, surfacing has one owner

"Started", "running", and "done" are different claims; done means
verified against a primary record (confirmation email, API response,
readback). For any given matter, the side holding the claim is the
side that reports to the human — the human's attention is a shared
budget; never spend it twice on the same item.

## 6. Acknowledge first; silence is never the safe default

A message from your human — or from a counterpart acting for theirs —
gets an immediate acknowledgement, even when you cannot yet act on
it: "received, confirming, answer by \<time\>" is always permitted
and never needs approval. Deciding may wait for a gate; replying may
not. Leaving the other side unread is the one response that is always
wrong: it reads as indifference, and it makes the sender escalate or
give up on the channel.
