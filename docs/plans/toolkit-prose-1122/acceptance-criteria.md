# Acceptance Criteria — toolkit-prose-1122

> Written before implementation. The closing Verify phase reconciles these
> against the test suite.

- **AC1** — Each line names one action and no line contradicts another in its file; the agent descriptions name every dispatcher; opencode ports are patched.
- **AC2** — Each listed paragraph is a list with one branch per item and each duplicate has one owner; rule-meter arms run on removed text; `bash tests/run.sh` passes.
- **AC3** — Each description reads "Designs backend/frontend features ... Dispatched by /eng-spec phase 4."; each duplicate has one owner in architect-core; rule-meter arms run; the opencode ports are patched.
- **AC4** — The body is the frontmatter plus at most four behavior-changing lines (reworded from "empty or one line" by agent-evals-c3, the item's owner, 2026-11-22); a rule-meter arm shows no loss; the opencode port is patched or knowingly skipped.
- **AC5** — None of the three _shared files the ticket names (skimmable-writing, design-decision-format, finding-log) remains with a single loader; adr-template.md, which skimmable-writing folds into, is out of scope and gets a follow-up queue item (agent-evals-c3, 2026-11-22) (plan-reading.md excluded: deferred to a follow-up item by agent-evals-c3, 2026-11-22; a script or gate that reads or cites a _shared file counts as a loader); every pointer names its trigger; each consumer list matches the loaders rg finds; `bash tests/run.sh` passes.
- **AC6** — One owner for the rule; the other file points to it or drops the sentence; rule-meter arms recorded in the change file; anchor rows updated; `bash tests/run.sh` passes.
- **AC7** — A seeded diff that adds a hard-coded toolkit-name list (skills, agents, hooks) to an app gets a reviewer finding that names the drift and the source the value can be derived from; the same diff without the rule gets none; a second seeded diff whose list has no other source in the tree gets no finding with the rule on.
- **AC8** — Running a skill or agent that was edited still loads every file it points to: no pointer, consumer list or gate message names a file that was folded away or deleted.
- **AC9** — Every rule that was cut, merged or reworded has a rule-meter on and off result, or is listed as unmeasured in the change file and reported to the orchestrating session.

## Manual only

- **AC10** — Opencode ports of the touched agents keep their own adaptations (AGENTS.md, frontmatter, "First action: Read") while carrying the same cuts; no automated test compares port drift by intent.
