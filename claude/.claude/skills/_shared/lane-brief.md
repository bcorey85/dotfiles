# Lane brief

A lane is a session started in its own worktree by `herdr-worktree` from its brief. Its brief names the task and the
orchestrating session, then points here. `<orchestrator>` below is that session's name.

## Report only to the orchestrator

- Send every question for the user, every ruling you need, every command for the user and your final report to
  `<orchestrator>` with SendMessage. Never ask in your own pane.
- If the user types in your pane, forward the request to `<orchestrator>` in your own words and go on.

## Run every phase through

- Run the plan from its first phase to its last: `/eng-spec`, then `/code`, then `/verify-branch`. Never code
  directly.
- Commit each phase on your branch when it passes, and go on to the next phase. A phase end is not a stop: never wait
  for a go-ahead to commit or start the next phase.
- Stop only for a decision the plan cannot settle, a hook that denies a step, or a failure after three attempts.

## Record rulings

Write each ruling `<orchestrator>` sends you as one line in the plan's `03-decisions.md`:

`Standing ruling by <who> at <YYYY-MM-DD>: <a short paraphrase, no quote marks> covers: rewords`

Use this form only for a ruling that covers rewording criteria. Log every other ruling in the decision log with who
ruled and when, in your own words.

## Toolkit edits

When the lane edits files under `claude/.claude/` in dotfiles:

- Give each behavior change a change file: `python3 ~/agent-evals/bin/build_changes.py new "<title>" --by
  claude-code/<model id> --root <worktree>/docs/changes`, then rerun `build_changes.py` with the same `--root`.
- A new or reworded rule in a skill, agent, rule file or CLAUDE.md needs rule-meter runs before it is committed:
  `~/agent-evals/bin/rule_meter.py run-all --rule <id>`. Put the per-arm counts in the change file's Result.
- For an anchored prompt file, update its row with `rule-anchors.sh list <file>`, then run `rule-anchors.sh check`.
- Never edit `settings.json`, any CLAUDE.md or `orchestration.md`. Send the proposed line to `<orchestrator>`.

## Checks under the memory cap

- Before a full suite or a heavy run, check `free -g`. Under 8 GB available, wait and tell `<orchestrator>`.
- Run the suite with a memory cap and in the background:
  `systemd-run --user --scope --quiet --slice=tests.slice -p MemoryMax=8G -p MemorySwapMax=0 bash tests/run.sh > <log> 2>&1`.

## Final report

At branch end, once the suite and lint pass, commit and push your branch:
`python3 ~/.claude/scripts/tools/pull_keep_index.py <worktree> && git -C <worktree> push -u origin HEAD`.
Then send `<orchestrator>` one message: the branch, the head hash, the suite count and failures, the items closed,
the items dropped with a reason each, and every ask still open.
