# Acceptance Criteria — code-skill-1122

> Written before implementation. The closing Verify phase reconciles these
> against the test suite.

## Item 1 — stopped /code fork's coder (ticket)

- **AC1** — TaskStop on a /code fork stops the dispatched coder, or its result names the live child id.
  Pending: ruled pending the settings.json line, which the user installs (ledger Resolved 6); not met until that line lands.
- **AC2** — A replay of a cancel during the coder step writes nothing after the stop.
- **AC3** — Asking for a fork's live children by the fork's id lists every coder or reviewer it started that has not finished, and does not list one that finished or was stopped.
- **AC4** — Asking for a fork's live children also stops that run's detached review loop, and does not touch a process that is not this run's review loop.
- **AC5** — Cancelling a fork with live children is refused once, naming each live child, and the second cancel goes through.
- **AC6** — Cancelling a fork with no live children, or stopping anything that is not a /code fork, behaves exactly as before.
- **AC7** — A broken or unreadable cancel check never blocks the user's cancel.

## Item 2 — hold drops mid-run (ticket)

- **AC8** — A file dirty at the phase start stays held for the whole phase even if its bytes change during the phase, and any change made to it during a coder call is named as a tool fault.
- **AC9** — An untracked file created by someone else during the phase (not by the run's coder) is not taken into the review scope.
- **AC10** — A test pins each case and fails without the change.
- **AC11** — A held file that the current phase also targets stays held and is named to the reader, not reviewed.
- **AC12** — When a held file's bytes differ from the phase-start record, the review prompt and the wait output say so, in words that name both the coder and the other session as possible writers.
- **AC13** — An untracked file the run's own coders wrote is still reviewed; with no other live session in the repo, scope is unchanged.
- **AC14** — A whole new untracked folder made by another session is held file by file, not as one folder entry.

## Item 3 — trim the skill's duplicated prose (ticket)

- **AC15** — The exact duplicates are cut, each reworded or removed rule has meter counts in its change file, and the text /code loads at start (SKILL.md plus the files it reads before phase end) is at least 10% shorter by word count, counting the template move from item 4; the change file records the before and after word counts.
  Reworded by agent-evals-c3 at the criteria walk, 2026-11-22 (was "the skill is 10-15% shorter").
  Premise ruled wrong (ledger D4): measured exact duplicates inside the /code load are 14 words, not 150-250.
- **AC16** — Every rule the skill stated before still reaches the /code run in the text it loads, except those the ledger names as cut.

## Item 4 — dedupe the stop rule, move the phase-end template (ticket)

- **AC17** — One owner per rule; dense paragraphs are lists; Block B lives in a sibling file read on a named phase-end trigger; rule-meter arms run on each cut; `bash tests/run.sh` passes.
  Bullet 4 (the acceptance_criteria-none rule) is split to another queue item by ruling, so "one owner per rule" excludes it here.
- **AC18** — A /code run that reaches a phase end reads the Phase-Complete template from its sibling file and produces the same block as before.
- **AC19** — A /code run that never reaches a phase end does not load the Phase-Complete template.

## Manual only

- **AC20** — With the settings.json line installed, a real TaskStop on a live /code fork with a running coder is refused and names the coder's id, and the coder writes nothing after the follow-up stop. No automated test can fire the real harness hook; the fixture is built from a transcript input until a captured event exists.
- **AC21** — The change file for each reworded /code sentence shows rule-meter on/off counts from real model runs. Meter runs call a live model and sit in a second repo.

## Coverage

Automated Verification line that tests each behavioral criterion (coverage: 18 mapped, 0 fixed of 19; AC2 and AC20-AC21 manual only, by ledger block 9).

| Criteria | Phase | Verification |
| --- | --- | --- |
| AC1 | 1 | `test_fork_children.py` hook deny case; pending the settings.json line (manual AC20 for the live cancel) |
| AC2 | manual | verified by the AC20 live run only (ledger block 9); the interrupted-reading unit test in `test_loop_transcript.py` stays but does not verify AC2 |
| AC3, AC4, AC5, AC6, AC7 | 1 | `test_fork_children.py` (children listing, loop pid route, one deny then pass, non-fork pass-through, fail-open) |
| AC8, AC11, AC12 | 2 | `test_phase_start.py`, `test_code_review_start.py`, `test_code_wait.py` (held through byte change, phase-target hold, tool-fault note) |
| AC9, AC13, AC14 | 2 | `test_code_review_start.py` (foreign untracked held, own-coder untracked reviewed, folder held per file) |
| AC10 | 2 | each Phase 2 test is written to fail on the base tree before the change (Testing Strategy) |
| AC15 | 3 | `skill_word_band.py` count check on the four-file start load (limit 3445); change file records the four before and after counts |
| AC16 | 3 | `test_code_skill_text.py`, `test_guidance_rules.py` (every kept rule still present in the loaded text) |
| AC17 | 3 | `rule-anchors.sh check`, `test_rule_anchors.py`, Phase 4 `bash tests/run.sh` |
| AC18, AC19 | 3 | Presence and Ban checks (`phase-end-block.md` exists, heading gone, trigger named); live read is Phase 3 Manual Verification |
