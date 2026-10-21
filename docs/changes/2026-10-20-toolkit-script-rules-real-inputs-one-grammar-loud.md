---
type: "Change"
title: "Toolkit script rules: real inputs, one grammar, loud failures"
description: "One rules file for every toolkit script and draft, loaded by the dotfiles and agent-evals project rules: read the real inputs first, one grammar per format with loud failures, check callers and real hook events, handle changes during a run, and test the draft and the installed copy."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-20T18:46:31-05:00"}
seq: 6
components: ["rule/toolkit-scripts"]
evidence: ["census", "judgment"]
watches: []
---

## Change

New file `docs/toolkit-script-rules.md`. The dotfiles `CLAUDE.md` imports it in place of its "Script tests" bullet, and the agent-evals `CLAUDE.md` imports it, so both repos that write toolkit scripts load it. Work repos do not load it. Sections:

- Read the real inputs first: collect the real files, list every shape, count work-machine shapes through the intake, and fix the whole class of a bug in one change.
- One grammar, loud failures: one parse function per format, a non-zero stop on any unparsed line, and a `check` command that runs where the text is written.
- Callers and events: test every caller before an output change, and code hooks against a captured real event.
- Changes during a run: list and test each mid-run change, and walk every state and verb in a termination test.
- Tests: one script-path variable, a test that fails without the change, "parsed N of M" over real inputs, and `tests/run.sh`.

The old "Script tests" bullet moved into the Tests section. Its code-step termination-test clause now covers every step script.

## Evidence

Census of the fix history of the toolkit scripts in the dotfiles git log and change files: 24 fixes.

| Cause | Fixes | Chains of 2+ fixes |
| --- | --- | --- |
| A real input shape the code did not handle | 6 | 1 |
| A step that repeated or did not stop | 4 | 1 |
| Output that broke a caller | 4 | 1 |
| Bad input passed with no error | 3 | 1 |
| Plain logic | 3 | 1 |
| Two readers of one format | 2 | 0 |
| A change during a run | 1 | 0 |
| Tests on the wrong copy | 1 | 0 |

Three bugs took 3 or more rounds. A commit gate assumed that the agent event carried the reviewer result, but the event fires at launch. code-step's plan-impact and asks paths took 4 rounds, one path per round, until a state-graph walk found 9 loops at once. comment-bloat-gate's regex was tuned on one input shape at a time.

Judgment from this session: the code-step closing-phase patch read "Phase 10.5" as Phase 10 because it was tested on plans the author wrote. Work plans also use ids such as 8.6b, P4 and 6A-6D. The main session adds phases and steps during a run. A test run against the installed copy of code-step showed 9 failures that were only the draft not yet installed.

## Result

Not measured. The rules load only in the dotfiles and agent-evals repos.

## Watch

None in the work logs: toolkit scripts are written on this machine. Count fix chains per script in the next census of the dotfiles history.

## Back-out

Delete `docs/toolkit-script-rules.md`, restore the "Script tests" bullet in the dotfiles `CLAUDE.md`, and remove the import line from the agent-evals `CLAUDE.md`.
