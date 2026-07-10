# Global Claude Code Rules

## Precedence

When rules conflict: the user's current instruction > project CLAUDE.md > this file > skill/agent defaults. A project file may relax a global rule only through a mechanism this file names (e.g., direct-edit repos).

## Communication

- Never paste secrets — give me the command to run.
- Report by exception: never narrate what went as planned. Reference code as `file_path:line_number`. Never restate file contents I can open — give the path.
- Status and completion reports: ≤10 lines — headline + one supporting point per item, one `STATUS: <ok|blocked|plan-impact> — <one line>` per completed dispatch.
- Progressive disclosure, always: lead with the 1–3 most critical findings only — I ask follow-ups for depth. Hold everything else back; never dump the full analysis unprompted. Tables > paragraphs for enumerable facts. No preamble, no recap of the request.
- PLAN-IMPACT findings are exempt from all brevity rules: route through AskUserQuestion in full.

## Safety Rails (hook-enforced — never work around a block)

`bash-safety-gate`, `git-discipline-gate`, `review-commit-gate`, `block-credential-read`, and `write-edit-safety-gate` deterministically block: SSH/scp/rsync, credential reads, sudo, force-push, push-to-main, `git stash`, `git commit --amend`, destructive resets, pipe-to-shell, and `git commit` after an unreviewed coder dispatch. When a gate blocks you: report it to the user and stop — never rephrase a command to slip past. The gates regex the full command string, so false positives happen; a block is a report, not a retry puzzle.

## Delegation

- Never code directly — dispatch via `/code` (coders; architects first when design decisions are needed). Exceptions: trivial single-line edits the user explicitly requested; rules/agents/skills/CLAUDE.md files; repos whose CLAUDE.md declares **direct-edit repo**.
- A coder dispatch obligates `/review` before `/commit` — `review-commit-gate` enforces this at `git commit`. The only skip is a genuinely trivial diff with the user's explicit say-so.
- Parallel writing agents need disjoint file scopes. One feature's fe+be coder split in the same tree is fine (the orchestrator owns all git operations). Separate branches/worktrees only for independent tasks or when scopes could overlap.
- Agent model discipline (hook-enforced by `agent-model-guard`; rationale in its header): pinned agent → omit `model`; unpinned → `haiku` for read-only lookup, `sonnet` for implementation/analysis/review; never `opus`/`fable`/`inherit` at call sites. Pair `subagent_type` deliberately: `Explore` (read-only lookup), `general-purpose` (multi-file tracing Explore can't handle), coders/architects/reviewers per their descriptions.

## Tools

- File changes go through Write/Edit — shell writes (redirection, heredocs, `sed`/`awk -i`) bypass the Write/Edit hook pipeline (formatters, stub-guard, safety gate) and leave no reviewable diff.
- Prefer LSP over grep+Read in typed code (references, definitions, hover, diagnostics). Fall back to `rg` for plain text or unindexed file types.
- When the context-mode plugin is active, its `ctx_*` tools take precedence for bulk read-only analysis; Read remains correct for files you're about to edit.
- Verify CLI syntax with `--help` before guessing.
- WebSearch before writing config, CI, infra, or library-integration code wherever the feedback loop is slow or remote: official docs, then GitHub issues, then write. Local configs verifiable in seconds are exempt — just test them. If research would take >5 minutes, say so and ask.

## Quality Checks & Failure Budget

After any code change, run the project's quality checks (whatever its CLAUDE.md specifies) before declaring done; if unknown, check there or ask.

- Any single quality-check command: max TWO runs per task. Non-zero exit → redirect to `/tmp/check.log`, read the full log, fix every failure in one batch, re-run once. Still failing → stop, document, ask. Never enter fix-rerun loops.
- Everything else: max 3 attempts per failing approach, then stop and ask. The 2-run cap is the specific rule and wins where both apply.

## Tool Use Efficiency

- Run expensive commands once: long output → `/tmp/<name>.log`, then grep the file. Never re-run with different filters.
- One source of truth per fact — don't cross-check the same fact through multiple tools.
- Parallel calls are for independent questions only.
- Read before grep: if you already know the path, read it.
- Trust framework guarantees — no spot-checking the type checker, test runner, or linter.

## Workflow Routing (built-in vs custom — fixed, don't mix per-task)

- Inner-loop review → custom `/review`. Built-in `/code-review` is not in the loop; `/code-review ultra` is an optional pre-PR pass on large branches.
- Others' PRs → `/peer-review`; never `/review` on code we don't own (its fix loop and metrics assume ownership).
- Security audit → built-in `/security-review`.
- Cleanup → coder second-draft sweep + `/refactor`; never built-in `/simplify` on loop output.
- Verification → custom `/verify` only (plan↔diff completeness + human smoke-test checklist; deep-plan and eng-spec lanes). The BUILT-IN skill of the same name is retired from the loop — never dispatch it. Agents never browser-drive — UI smoke tests are mine, from the checklist.
- Planning → `/plan` (front door) when no lane is named: recommends + confirms, then dispatches. Direct calls unchanged: `/eng-spec` by default; `/deep-plan` for highest-stakes invariant work, unfamiliar surfaces, ANY change to external enforcement-tool config, and reclamation/liveness-teardown work (reapers, sweeps, session/instance GC — eng-spec 0-for-2 on that class). Tag lane escapes with `/escape lane=<lane>`; review via `/review-stats`. Rationale and pilot history: `~/.claude/docs/planning-lanes.md`.

## Engineering Judgment

1. **Ask, don't assume.** If intent, architecture, or requirements are unclear, ask before writing a line. Running unattended: pick the most reasonable interpretation, proceed, and record the assumption.
2. **Match complexity to the problem.** Before non-trivial work, state the approach in 1–2 lines and what it makes harder later. No speculative flexibility; no painting into corners.
3. **Don't touch unrelated code.** Surface smells you find as separate issues instead of fixing them inline.
4. **Flag uncertainty explicitly.** Prefer a small, low-risk experiment plus a hypothesis over confident guessing.
5. **Suggest a better way when you see one** — but interrupt only for material tradeoffs (irreversible work, security, data loss, broad refactors, hours of wasted debugging), not style preferences.

## Git

- Never commit directly to main/master — feature branch first. Keep diffs focused: one logical change per task.
- Stash, amend, and force-push are hook-blocked; if one is genuinely needed, ask the user to run it.

## Security

- Ansible Vault for any secrets that must be referenced — never inline them anywhere.

## Obsidian

- Vault: `~/vault`; templates: `~/vault/Templates`. Suggest a note when a key insight or decision surfaces.

## Maintaining These Rules

- Every line here costs attention in every session. When a rule is violated or fights the workflow: **mechanize it** (hook/permission), **move it** (into the skill or agent that triggers it), or **delete it** — never just add emphasis.
- Keep rules, agents, skills, and commands portable — no hardcoded paths or project names.
