# Acceptance Criteria — code-gates-1123

> Written before implementation. The closing Verify phase reconciles these
> against the test suite.

## Ticket item 1

- **AC1** — A check fails a /code fork's hand-back when the run folder holds no review packet for the phase (or a recorded reason the step allows), and passes when the review ran. A test in tests/scripts pins both cases.
- **AC2** — A /code fork that ends after a coder dispatch with no review is told to run the review before it finishes.
- **AC3** — A /code fork that dispatched a coder, then ended with no review run of its own and no stop file written after the dispatch, is sent back once.
- **AC4** — A /code fork that wrote a stop file after its coder dispatch is not sent back for missing review.
- **AC5** — A /code fork that never dispatched a coder is never sent back for missing review.
- **AC6** — A review packet or stop file left in the run folder by an earlier run does not let a fork that skipped review through.
- **AC7** — A fork that is sent back once and stops again is not sent back a second time (no block loop).

## Ticket item 2

- **AC8** — A test: a transcript where the turn launched a `run_in_background` Bash call and an Agent call, and the final text says "is running", passes the gate. A turn that launched nothing still gets sent back.
- **AC9** — A status line that says nothing is running, on a turn that launched nothing, is sent back with the same reason as before.
- **AC10** — A turn that launched background work and ends with "a new agent is working on it" (the incident sentence) passes the gate.
- **AC11** — A first-person announcement ("I'll run the suite") still gets sent back even when the turn launched background work.
- **AC12** — A background launch from an earlier turn does not excuse a progress line in a later turn.
- **AC13** — A crash in one stop check is reported on stderr and does not drop the reasons the other stop checks give (including the staged-claim reason).

## Ticket item 4

- **AC14** — A test records a check piped into `rg` (and `rg -A`) as cut, then allows one rerun redirected to a file; the test fails while `OUTPUT_FILTER_START` lists only tail, head and grep.
- **AC15** — After a check piped into `rg`, a second rerun that is not redirected to a file is still denied.
- **AC16** — The deny message tells the user that tail, head, grep or rg cut the output.

## Out of scope

- Ticket item 3 (inline python heredoc that rewrites an untracked source file passes every gate) left this plan. Ruled by agent-evals-c3-owner (orchestrating session), 2026-11-23, recorded in ledger block 5: the auto-mode gate pilot is a live experiment read on 2026-11-29 and 2026-12-06, and a new deny would add a second variable. The item returns to the queue; its Done-when is not met by this branch and no criterion here claims it.

## Manual only

- **AC17** — A real /code fork that codes and skips review is sent back at its actual stop, not only in a synthetic event; no automated test can cover it because the real stop event for a fork has never been captured and the tests use a made-up payload.
