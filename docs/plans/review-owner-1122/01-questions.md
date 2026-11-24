# Research Questions

1. How does `claude/.claude/scripts/review/review_loop_ruled.py` decide what to do with each file a review fix pass changed? Trace the flow from the changed-file list to the keep, revert and ask outcomes.
2. Which files and path patterns does the review loop treat as approval-only, and where is that list defined and consumed?
3. How are protected or sign-off lines handled when a fix pass edits a file (`lib/protected_lines.py`, `lib/signoff_lines.py`, `review/review_loop_signoffs.py`)? What data structures represent a changed line and its classification?
4. How does a run's decision log (`03-decisions.md`) record rulings, and which modules read it (`lib/standing_rulings.py`, `lib/ruled_change_text.py`, `lib/ask_outcome_words.py`)? What does a session ruling look like on disk and how is it told apart from a user ruling?
5. What lines does `claude/.claude/scripts/CLAUDE.md` contain today, what shapes do its bullet lines take, and how do its entries point at the module that owns a fact?
6. What tests exist under `tests/scripts/` for `review_loop_ruled.py` and the related review-loop mixins, what fixtures and helpers do they use, and how does `tests/scripts/toolkit_paths.py` resolve script paths?
7. How does `plan_check.py owner` determine the criteria owner of a plan? Which ticket-text patterns (queue `Source:` line spellings, criteria headings) map to `user`, `session` and `plan`?
8. What does `claude/.claude/skills/eng-spec/phases/1-ticket.md` instruct, step by step, about snapshotting the ticket and writing a `Source:` line? What helper scripts does it call?
9. How are queue item files located and read (`~/agent-evals/queue/`, `bin/build_queue.py`), and which toolkit scripts refer to a queue item path?
10. How does the rule-meter harness (`~/agent-evals/bin/rule_meter.py`, `rule_meter_scenarios.json`, `bin/rule_meter_checks/`) define scenarios, arms and detectors, and what is the `toolkit_root` field?
11. What is the convention for change files in `docs/changes/` (naming, kinds, required fields), and how are they validated?

## Exploration Map

- `claude/.claude/scripts/review/review_loop_ruled.py` — fix-pass file handling and revert logic
- `claude/.claude/scripts/lib/` — protected lines, sign-off lines, standing rulings, ruled-change text
- `claude/.claude/scripts/review/review_loop_signoffs.py` — sign-off line protection in fix passes
- `claude/.claude/scripts/CLAUDE.md` — shape of existing lines
- `claude/.claude/scripts/code/plan_check.py` and `lib/plan_format.py` — owner determination
- `claude/.claude/skills/eng-spec/phases/1-ticket.md` — ticket snapshot and Source line steps
- `tests/scripts/` and `tests/scripts/toolkit_paths.py` — existing test patterns
- `docs/changes/` — change file conventions
- `~/agent-evals/bin/` and `~/agent-evals/queue/` — rule-meter harness and queue files
