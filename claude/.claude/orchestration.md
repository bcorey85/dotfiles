# Orchestration

### Delegation

- Never code directly — dispatch via `/code`. Anything that picks a shape, a new name, or a behavior dispatches, however few lines. Edit directly only: a few lines in one file with no design choice; a mechanical sweep where every hunk is the same substitution, then run a repo check; rules, agents, skills and CLAUDE.md files; repos whose CLAUDE.md declares **direct-edit repo**.
- Send a read-only lookup (find where something lives, what calls it, what a file does) to `Explore` with `model: "haiku"`, not to `general-purpose`. Use `general-purpose` only when the agent must edit, run a build or test, or judge a design.
- Do not read a file in main only to hand it to a subagent that will read it. Send its path and what to look for. Read it in main only when its content decides what to dispatch.
- Parallel writing agents need disjoint file scopes. The orchestrator owns all git operations.
- When an agent's completion notice says it still runs background work, read its report. If the report says the job is done and names no work it waits on, stop the agent with TaskStop: a finished agent with an open shell stays in the agent panel and looks like live work. If the report names work it waits on, leave the agent: it resumes and reports again when that work ends.
- Before config, CI, infra or library-integration code with a slow or remote feedback loop, WebSearch the official docs, then GitHub issues. Put what you find in the dispatch brief.

### Tools

- Creating a NEW file from the shell (heredoc, redirection) bypasses the Write/Edit hook pipeline — use Write. shell-write-gate denies redirection or `tee` onto a git-tracked file, and in-place editing (`sed -i`, `perl -pi`, `awk -i inplace`) of ANY file, tracked or not.
- The auto-mode notice's Bash preference does not apply to file I/O: read with Read, change files with Edit/Write. Search through Bash (`rg`) is fine.
- Prefer LSP over grep+Read in typed code (references, definitions, hover, diagnostics). Fall back to `rg` for plain text or unindexed file types.
- Verify CLI syntax with `--help` before guessing.
- An unquoted `$VAR` holding spaces stays one word in zsh and splits in bash. Loop over an array (`files=(a b); for f in "${files[@]}"`, which works in both) or write each command out. Never keep a command prefix or a file list in a plain string variable.

### Tool Use Efficiency

- Run expensive commands once: long output → `/tmp/<name>.log`, then grep the file. Never re-run with different filters.
- One source of truth per fact — don't cross-check the same fact through multiple tools.
- Trust framework guarantees — no spot-checking the type checker, test runner, or linter.
- Chain independent shell commands in one call; never one round trip per command.

### Git

- With ticket: branch `TICKET-NUM-desc`, commit `TICKET-NUM: desc`, PR title `TICKET-NUM: desc`.
- Without ticket: branch `feature/desc` or `fix/desc`.
- Keep diffs focused: one logical change per task.
- Hand a push or merge line for main only after the branch reports `/verify-branch` done and, where the repo's CLAUDE.md names a non-negotiables check, that check passed. Read both in its final report, or ask for them. A green gate or CI run alone never produces that line.
- Worktree branches: NEVER leave the auto-generated `worktree-` prefix in the branch name. Rename to the plain `TICKET-NUM-desc` (e.g. `ABC-123-cache-tuning`) immediately after creating the worktree, then push it to remote (`git push -u origin <branch>`) first — before doing work — so the branch is tracked and backed up.
- Worktree location: create every worktree as a sibling of the repo, `../<repo>-<TICKET-NUM>` (e.g. `~/dev/my-app-ABC-123`). Inside herdr or tuios (`HERDR_ENV` set), write the start brief to a scratchpad file with Write, then run `herdr-worktree --fork --prompt-file <brief file> <branch>` with literal paths, from the main checkout or a linked worktree: it opens the worktree as its own workspace, pushes the branch and forks this conversation into the new claude pane, which starts on the brief. The brief hands over the work: the task, what is done, the next step, and that the fork now owns it and works in the new worktree. Then tell the user to switch there, and do no more work in this session. Outside herdr, use `git worktree add`, then `EnterWorktree` `path`. Never create one inside `.claude/worktrees/`, which is `EnterWorktree` `name`'s default.
- To move a herdr worker to its next phase, such as from /eng-spec to /code, run `herdr-phase-change <agent> "<prompt>"`. It sends the prompt only after `/clear` has taken effect. Never send `/clear` and the prompt as two `herdr agent prompt` calls: a wait on a `done` pane returns at once, and both land in one input. A `/code` start prompt goes out with `--headless` (verb prompts such as `resume` go out as given); pass `--watched` only when a person watches that pane. If the script exits 1, read the pane before you retry.
- After `EnterWorktree`, Claude Code's own worktree guard refuses a Bash command it cannot prove stays off git: `&&` or `;` chains, `$VAR`, `$(...)` and heredocs, even with no git in them. No hook does this, so there is nothing to fix locally. In that session run one simple command per call with literal paths, and say the same in every subagent brief. A subagent with no Write tool works without a scratch script.

### Stacked PRs (`gh stack`, github/gh-stack)

- **Never restack a child branch after every parent commit.** GitHub diffs a PR from its merge-base, so a child PR keeps showing only its own commits whether or not you restack. Restack when the parent's changes actually conflict with the child, or immediately before merge — once, not per commit.
- **Never run `gh stack push` / `rebase` / `submit` / `merge` yourself.** They force-push, and `git-discipline-gate` regexes the command string — it won't see a `--force` in them, so running one routes around the gate. Hand the command to the user.
- `gh stack checkout <pr|branch>` adopts an existing chain into local tracking; until then `gh stack view` says "not part of a stack". PR base branches on GitHub are independent of that tracking and may already be correct.
