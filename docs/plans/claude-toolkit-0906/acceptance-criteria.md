# Acceptance Criteria — claude-toolkit-0906

> Written before implementation. The closing Verify phase reconciles these
> against the test suite.

- **AC1** — Running a project's quality-check command (test/lint/typecheck/etc.) a second time with no file edit in between is denied, and the denial tells you to redirect the failing run to a log, read the whole log, fix every failure in one batch, and re-run once.
- **AC2** — After editing any file, re-running that same quality-check command succeeds instead of staying denied.
- **AC3** — Trying to write to a git-tracked file from a shell command (`>`, `>>`, `tee`, or an in-place editor like `sed -i`) is denied, and the denial names the file and says to use the Edit/Write tool instead.
- **AC4** — Writing to an untracked or scratch path from the shell **by redirection or `tee`** (e.g. `/tmp/...`, a new file, build output) still works exactly as before. **In-place editors are excluded** — `sed -i`/`perl -i`/`awk -i inplace` are denied unconditionally, on tracked and untracked paths alike (decision 4; see Divergences).
- **AC5** — Attempting to `git commit` or `git push` while the current branch still carries the auto-generated `worktree-` prefix is denied, naming the branch and telling you to rename it.
- **AC6** — The review-before-commit gate and the git-discipline gate now refuse a commit by explicitly denying it (visible reason given), and a bug inside either gate's own script blocks the commit instead of silently letting an unreviewed or rule-breaking commit through.
- **AC7** — In a brand-new session, and again right after a long session compacts, the model already knows the workflow-routing rules (which lane handles a given kind of work) without having to read any file for it.
- **AC8** — The root CLAUDE.md is visibly shorter: its Communication, Orchestration, and Git sections are gone from that file, and asking where that content went points to where it actually now lives.
- **AC9** — `/output-style` shows a "Laconic" style available and active, carrying the same terseness rules the old Communication section stated.
- **AC10** — The caveman plugin is gone from the running session: no persona text at session start, and `/caveman` is no longer a usable command.
- **AC11** — Logging a review finding with `fix_induced=bug` always ends up recorded as a blocking finding, even if the caller didn't say so explicitly.
- **AC12** — Writing a hardcoded absolute path or the literal word "dotfiles" into an agent, skill, or command file produces a warning at write time but does not block the write.
- **AC13** — Running the toolkit's doctor script reports whether each new gate is registered, whether each `rules/*.md` file is well-formed, and whether the orchestration content is actually wired up — and it exits cleanly on a healthy tree.
- **AC14** — Every new deny-capable gate this change adds behaves the same way whether the session is running under Claude Code directly or under the omp/Oh My Pi harness.
- **AC15** — The opencode port of `code-reviewer.md` catches up to the current claude-side reviewer's rules (comment-density check, the broadened vocabulary list) while keeping opencode's own required differences (AGENTS.md wording, no Persistent Memory instruction, its model/permission/color settings).
- **AC16** — No file left in the repo still refers to a rule, script, or section name this change removed or renamed.

## Manual only

- **AC17** — Whether the Laconic output style visibly changes day-to-day chat responses — this is the ticket's own kill condition (if it doesn't visibly change output, the next pass deletes it rather than relocating it again), and it can only be judged by the user's impression over normal use, not by an automated check.
- **AC18** — Dispatching a subagent and confirming, from its actual behavior, that it did _not_ receive the orchestration/workflow-routing content — this is an absence-of-effect check on a live subagent dispatch, not something a unit test asserts.
- **AC19** — Restarting Claude Code and visually confirming the session-start banner carries no caveman persona text and that `/caveman` no longer appears in the command list — requires an actual running session to look at, not scriptable from outside it.

## Open — ticket-owner's call

- ~~If a false deny happens on `quality-check-cap` or `shell-write-gate`, is session-wide `CLAUDE_SKIP_HOOKS` an acceptable unblock, or does each gate need a narrower override?~~ **Resolved** — decision 17 chose a narrow per-gate escape; decision 38 replaced the env-variable form with an in-band command token (`#skip-quality-cap`, `#skip-shell-write-gate`) after the variable form proved unable to reach a PreToolUse hook at all.
- If `quality-check-cap`'s state directory becomes unwritable, the plan denies _every_ quality-check command outright (not just repeats) until it's fixed, rather than allowing runs through — is a total block the wanted failure mode here, or should this specific failure fail open instead?
- If the SessionStart orchestration injection silently stops working (hook unregistered, `orchestration.md` missing or unreadable), nothing detects it except a manually-run doctor pass — is that an acceptable detection gap, or should something check this automatically at session start rather than only on demand?

## Divergences

- **AC4's scratch-path allowance does not extend to in-place editors.** `sed -i /tmp/scratch.txt` is denied even though the path is untracked — decision 4 made in-place editing unconditional, because the flag itself is the bypass and target-tracking is not what makes it one. AC4 above is worded to match; a verifier walking AC4 with an in-place editor on a scratch path is testing the wrong form and should use a redirect.

- **AC14 is verified structurally, not behaviourally, for the omp half.** Every automated check greps `claude-security-bridge.ts` for the gate name and branch shape; none starts an omp session. AC14's manual item is the only behavioural check, and it must actually be run — see the plan's External Contracts note on the declared-only assumption that omp emits a `tool_result` for the `bash` tool with `input.command` populated.

- The ticket names the coder/code-reviewer agents (`coder.md`, `coder-deep.md`, `code-reviewer.md`, `code-reviewer-deep.md`) as the primary surface to mechanize. The finalized plan makes **no rule changes at all** to any of the four (the sole edit is a one-phrase dangling-pointer deletion in both `code-reviewer.md` copies — decision 28) — the decision ledger (items 8, 10, 11) concluded almost nothing in those bodies has a deterministic oracle, and the mechanizable content they depend on lives in `coder-core`, `settings.json`, and standalone scripts instead. This was resolved through the decision process (not an oversight), but it means an AC reading "the coder/code-reviewer agent files themselves are mechanized" would be false to what's being shipped — the criteria above test the underlying mechanisms (quality-check cap, shell-write gate, orchestration/communication relocation, doctor checks) rather than edits to those four files.
