# Lane 7: gate messages and /code fork bugs

Fix the queue items below. Each phase starts with a test that fails on the current tree.

## Scope

- In: `claude/.claude/scripts/gates/comment_bloat_gate.py` (deny names the marker),
  `claude/.claude/scripts/gates/permission_question.py` (a ticket filing question passes),
  `claude/.claude/scripts/gates/git_discipline_gate.py` (the push rule's pull form passes),
  `claude/.claude/skills/code/SKILL.md` and `claude/.claude/agents/code-fork.md` (stopping a fork, queue-item
  done-clauses), and their tests in `tests/scripts/`.
- Out: `claude/.claude/CLAUDE.md` (the push rule is the user's words), `review_commit_gate.py`, `handback.py`, the
  review loop's fix-removed-change check, `settings.json`, any `~/agent-evals/` file.

## Phase Status

- [x] Phase 1: gate denies name their cause, and the push rule's pull passes (risk: low)
- [x] Phase 2: /code fork stop and queue-item done-clauses (risk: low)

## Phase 1: gate denies name their cause, and the push rule's pull passes

1. `comment_bloat_gate.py`: the marker deny names the text each line matched. `marker_hit` returns the first matched
   text (`match.group()`) or None in place of a bool; `marker_rows` yields `(number, line, marker)`. Each deny line
   reads `  <number>:<line>  <- marker "<matched text>"`. The rest of the deny text stays.
2. `permission_question.py`: a closing question that files, opens, creates or raises a ticket passes when the ticket
   noun carries a prefix (`sub-tickets`, `subtickets`, `subtasks`, `sub-issues`) or names the tracker (`Jira`,
   `Linear`, `GitHub`) right after `in`/`on`/`to`/`into`. Extend `OUTWARD_STEP` only:
   `(?:sub-?)?(?:tickets?|issues?)|sub-?tasks?` after the ticket verb (a bare `task` is not a ticket noun), and
   `\b(?:file|open|create|raise)\b[^?]*?\b(?:in|on|to|into)\s+(?:jira|linear|github)\b` as an outward place; `slack`
   stays bare. Update the module docstring's list. A question about a local step (`Want me to rerun the tests?`,
   `Want me to add the test?`) still blocks.
3. `git_discipline_gate.py`: a `git pull` with `--autostash` passes when the next git call in the same command is a
   `push` in the same directory; that is the push rule's form (`git -C <repo> pull --rebase=merges --autostash &&
   git -C <repo> push`). Every other autostash stays denied: a lone `pull --autostash`, `rebase`/`merge
   --autostash`, and the autostash config. Update docstring rule 1 and the autostash deny text to name the allowed
   form. Add an allow row to `tests/scripts/gate_replay_corpus.json` for the rule's form; keep
   `gdg-pull-autostash` as a deny.

#### Automated Verification

- New tests, each failing on the current tree: the marker deny names `phase 2` beside its line
  (`test_comment_bloat_gate.py`); `Want me to file the per-domain sub-tickets?` and `Want me to file them in Jira?`
  pass the staged-claim Stop gate while `Want me to rerun the tests?`, `Want me to make the lookup linear?` and
  `Want me to open the task file?` still block (`test_staged_claim_gate.py`);
  `git -C /r pull --rebase=merges --autostash && git -C /r push` passes, `git pull --rebase=merges --autostash` alone
  and `git -C /a pull --autostash && git -C /b push` are denied (`test_git_discipline_gate.py`).
- `python3 tests/parallel_tests.py test_comment_bloat_gate.py test_staged_claim_gate.py test_git_discipline_gate.py`
  and the gate replay corpus test pass; `bash tests/lint.sh` on the three changed .py files passes.

## Phase 2: /code fork stop and queue-item done-clauses

Prompt edits only; a coder makes them.

1. `skills/code/SKILL.md` frontmatter `description` (the caller reads it): add one sentence: to cancel a running
   /code fork, SendMessage it `stop` and wait for its stop; TaskStop the fork only after that stop names every agent
   it dispatched as stopped.
2. `agents/code-fork.md`: add: when a message says stop or cancel, TaskStop every agent you dispatched that still
   runs, then end the run with a stop that names each agent id and says it is stopped.
3. `skills/code/SKILL.md` line 34 (`Plan impacts never stop the run`): the sign-off rule covers ticket ACs and
   eng-spec criteria. Add: in a plan built from a queue item with no ticket, a criterion that restates the item's
   done-clause changes on the orchestrator's ruling when the queue item or the brief records it; a coder logs it under
   `## Plan Deviations` with who and the date, and the run goes on. Keep the sentence that a brief is never the user's
   sign-off for a ticket AC.
4. Add guidance tests in `tests/scripts/test_guidance_rules.py` for 1–3, and patch the opencode port of code-fork if
   one exists under `opencode/.config/opencode/agents/`.

#### Automated Verification

- New guidance tests fail on the current tree and pass after.
- `python3 tests/parallel_tests.py test_guidance_rules.py` passes; `~/.claude/scripts/tools/rule-anchors.sh check`
  passes from the worktree.

## Plan Deviations

- Phase 1 step 2: OUTWARD_STEP tracker branch needs a filing verb (file|open|create|raise) plus a pronoun object (them|these|those|this|it|each) right before in|on|to|into a tracker name (jira|linear|github); task only as sub-?tasks?; no criterion changed; AC2 text matches the code.
- Phase 1 step 3: the pull passes only when the next step is joined to it by `&&` and opens with the `push` in the same directory (a `;`, `||`, newline or an intervening step denies), the pull carries the literal `--autostash` flag (not `-c rebase.autoStash=true`), and neither step holds a `$(...)`, backtick or parenthesis; adopted by the session, 2026-11-07, no criterion changed.
