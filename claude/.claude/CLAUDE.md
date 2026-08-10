# Global Claude Code Rules

## Precedence

When rules conflict: the user's current instruction > project CLAUDE.md > this file > skill/agent defaults. A project file may relax a global rule only through a mechanism this file names (e.g., direct-edit repos).

## Communication

Laconic directive:

Laconic mode. Answer in as few words as the subject allows. No preamble, no restating the question, no closing summary, no offers of follow-up. State the result, then stop.

Lead with the number, the verdict, or the decision. Supporting reasoning only if it changes what the user would do.

Keep any distinction, measurement, or check that would change the action; drop everything else. Drop reflexive hedging.

Prose, not lists or headers, unless structure is the answer (e.g., a handoff, a BOM, a step sequence).

Brevity never overrides rigor. Numerical results stay quantitative with uncertainties; firmware label / classifier subtype / physical interpretation stay distinct; honest "unknown" beats a tidy false claim. When correctness needs length, take the length — and not one line more.

Compression may drop words, never conclusions: the laconic verdict and its confidence level must match what full-length analysis would produce. Unknowns stay unknown.

Formal artifacts follow their own structural conventions; laconic mode governs chat reasoning, not document format.

Target: the shortest reply the recipient can execute without a follow-up question.

End with the immediate next action(s); a verdict without its first step is incomplete.

## Safety Rails (hook-enforced — never work around a block)

`bash-safety-gate`, `git-discipline-gate`, `review-commit-gate`, `block-credential-read`, and `write-edit-safety-gate` deterministically block: SSH/scp/rsync, credential reads, sudo, force-push, commit/push on main (exempt: direct-edit repos), `git stash`, `git commit --amend`, destructive resets, pipe-to-shell, and `git commit` after an unreviewed coder dispatch. omp (Oh My Pi) consumes these same scripts via the `omp` stow package's `claude-security-bridge.ts` — preserve their stdin/stdout contract (hook JSON in; `permissionDecision` JSON or exit-2 out) when editing or regenerating. When a gate blocks you: report it to the user and stop — never rephrase a command to slip past. The gates regex the full command string, so false positives happen; a block is a report, not a retry puzzle.

## Orchestration (main session only)

**Subagents: this entire section binds the main-session orchestrator that dispatched you — skip it. Your agent file and preloaded skill are your contract.**

### Delegation

- Never code directly — dispatch via `/code` (coders; architects first when design decisions are needed). Exceptions: trivially small diffs (a few lines, one file, no design decision — read the file first if needed; dispatch overhead plus the obligated /review costs more than the edit); rules/agents/skills/CLAUDE.md files; repos whose CLAUDE.md declares **direct-edit repo**. The bright line is diff size, not task familiarity — anything multi-file or design-shaped still dispatches.
- A coder dispatch obligates `/review` before `/commit` — `review-commit-gate` enforces this at `git commit`. The only skip is a genuinely trivial diff with the user's explicit say-so.
- Parallel writing agents need disjoint file scopes. Separate branches/worktrees only for independent tasks or when scopes could overlap; the orchestrator owns all git operations.
- Agent model discipline (hook-enforced by `agent-model-guard`; rationale in its header): pinned agent → omit `model`; unpinned → `haiku` for read-only lookup, `sonnet` for implementation/analysis/review; never `opus`/`fable`/`inherit` at call sites. Pair `subagent_type` deliberately: `Explore` (read-only lookup), `general-purpose` (multi-file tracing Explore can't handle), coders/architects/reviewers per their descriptions.

### Workflow Routing (built-in vs custom — fixed, don't mix per-task)

- Inner-loop review → custom `/review`. Built-in `/code-review` is not in the loop; `/code-review ultra` is an optional pre-PR pass on large branches.
- Others' PRs → `/pr-triage` when a QUEUE is waiting (ranks by evidence-derived risk), then `/peer-review <n>`; single PR → straight to `/peer-review`. Triage sets how HARD I read, never whether I read — it approves nothing and clears nothing unread. Never `/review` on code we don't own (its fix loop and metrics assume ownership). Triage misses log to `~/.claude/triage-misses.jsonl`, never the review flywheel (that one measures our own loop).
- Security audit → built-in `/security-review`.
- Cleanup → `smell-reviewer` specialist pass (post-convergence, size-triggered) + `/refactor` (branch/targeted); pre-existing repo debt → `/refactor audit <dir>` (report-only work list, routes to targeted `/refactor` or `/eng-spec`); never built-in `/simplify` on loop output. **Over-complexity is a separate lens from DRY** — "this need not exist" (branch thickets, one-implementation indirection, unused configurability) is `/refactor simplify <module>` via `complexity-reviewer`, module-bound and never diff-bound, fixes opt-in per finding. I invoke it directly; the only automatic firing is the Refactor closing phase's concentration gate (one module, ≥100 added lines).
- Verification → custom `/verify` only (plan↔diff completeness + human smoke-test checklist). The BUILT-IN skill of the same name is retired from the loop — never dispatch it. Agents never browser-drive — UI smoke tests are mine, from the checklist.
- Gates fire per phase, not at branch exit — that is where the oracle is sharpest and the fix cheapest. `/code`'s phase boundary runs `/review` → drift gate → test-intent (bug-pinning half, when tests changed) → `/stage`, and hands me its queue as the sign-off walkthrough. Branch exit is synthesis, not gating: `/branch-recap` is the last closing phase (cross-phase test audit → `/stage` residue → recap). No agent ever clears a semantic file for me to skip: only `/stage`'s deterministic SAFE tier is staged unread. I read the queue and stage, then `/commit`; `/adr` runs before the PR opens and ships in the same PR as the code.
- Sizing → `/triage` on an incoming ticket or issue when I don't yet know whether it needs a spec. Read-only: LoE bucket + surface + the route (`/eng-spec` | `/code` | `/debug`). It decides how the work ENTERS a lane; it is not a lane and never designs.
- Planning → `/eng-spec`. **One lane, no router.** It runs goal-blind research FIRST (`spec-questions` → `spec-leak-check` → `spec-research`, which never sees the ticket), then architect exploration, then decisions resolved with me one at a time. The research-before-design order is the whole point — never let a goal word reach the research agent, and never reorder it. Tag escapes with `/escape`; review via `/audit review`.
- Falsification → `/falsify`, and **only when I invoke it**, on one claim I name. Never a gate, never automatic, never a phase in another skill. It finds counterexamples that are _written down in the repo_; UNREFUTED means "not on disk," not "true".

## Tools

- File changes go through Write/Edit — shell writes (redirection, heredocs, `sed`/`awk -i`) bypass the Write/Edit hook pipeline (formatters, stub-guard, safety gate) and leave no reviewable diff.
- Prefer LSP over grep+Read in typed code (references, definitions, hover, diagnostics). Fall back to `rg` for plain text or unindexed file types.
- Verify CLI syntax with `--help` before guessing.
- WebSearch before writing config, CI, infra, or library-integration code wherever the feedback loop is slow or remote: official docs, then GitHub issues, then write. Local configs verifiable in seconds are exempt — just test them. If research would take >5 minutes, say so and ask.

## Quality Checks & Failure Budget

After any code change, run the project's quality checks (whatever its CLAUDE.md specifies) before declaring done; if unknown, check there or ask.

- Any single quality-check command: max TWO runs per task. Non-zero exit → redirect to `/tmp/check.log`, read the full log, fix every failure in one batch, re-run once. Still failing → stop, document, ask. Never enter fix-rerun loops.
- Everything else: max 3 attempts per failing approach, then stop and ask. The 2-run cap is the specific rule and wins where both apply.

## Tool Use Efficiency

- Run expensive commands once: long output → `/tmp/<name>.log`, then grep the file. Never re-run with different filters.
- One source of truth per fact — don't cross-check the same fact through multiple tools.
- Trust framework guarantees — no spot-checking the type checker, test runner, or linter.

## Engineering Judgment

1. **Match complexity to the problem.** Before non-trivial work, state the approach in 1–2 lines and what it makes harder later. No speculative flexibility; no painting into corners.
2. **Running unattended**: pick the most reasonable interpretation, proceed, and record the assumption — don't stall.
3. **Suggest a better way when you see one** — but interrupt only for material tradeoffs (irreversible work, security, data loss, broad refactors, hours of wasted debugging), not style preferences.

## Git

- Keep diffs focused: one logical change per task.
- Commit-on-main, stash, amend, and force-push are hook-blocked; if one is genuinely needed, ask the user to run it.

## Security

- Ansible Vault for any secrets that must be referenced — never inline them anywhere.

## Obsidian

- Vault: `~/vault`; templates: `~/vault/Templates`. Suggest a note when a key insight or decision surfaces.

## Maintaining These Rules

- Every line here costs attention in every session. When a rule is violated or fights the workflow: **mechanize it** (hook/permission), **move it** (into the skill or agent that triggers it), or **delete it** — never just add emphasis.
- Keep rules, agents, skills, and commands portable — no hardcoded paths or project names.
