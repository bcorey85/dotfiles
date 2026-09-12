# Global Claude Code Rules

## Precedence

When rules conflict: the user's current instruction > project CLAUDE.md > this file > skill/agent defaults. A project file may relax a global rule only through a mechanism this file names (e.g., direct-edit repos).

## Safety Rails (hook-enforced — never work around a block)

`bash-safety-gate`, `git-discipline-gate`, `review-commit-gate`, `shell-write-gate`, `block-credential-read`, and `write-edit-safety-gate` deterministically block: SSH/scp/rsync, credential reads, sudo, force-push, commit/push on main (exempt: direct-edit repos), `git stash`, `git commit --amend`, destructive resets, pipe-to-shell, shell writes to tracked files or (for coders) test files, and `git commit` after an unreviewed coder dispatch. omp (Oh My Pi) consumes these same scripts via the `omp` stow package's `claude-security-bridge.ts` — preserve their stdin/stdout contract (hook JSON in; `permissionDecision` JSON or exit-2 out) when editing or regenerating. When a gate blocks you: report it to the user and stop — never rephrase a command to slip past. The gates regex the full command string, so false positives happen; a block is a report, not a retry puzzle.

Workflow gates (advisory, not rails — their deny message says what to do next, and each has a narrow escape you append to the command as a comment, on the user's say-so): shell-write-gate (`#skip-shell-write-gate`; never disarms its test-ownership check), quality-check-cap (`#skip-quality-cap`).

## Where the rest lives

Orchestration and workflow routing live in `~/.claude/orchestration.md`, injected at session start. Main session only — subagents never receive them.

Prose style lives in the `Laconic` output style (`~/.claude/output-styles/laconic.md`). Main session only.

Git conventions — branch and commit naming, focused diffs, worktree branches, stacked PRs — live in `~/.claude/rules/git.md`.

## Tools

- Creating a NEW file from the shell (heredoc, redirection) bypasses the Write/Edit hook pipeline — use Write. shell-write-gate denies redirection or `tee` onto a git-tracked file, and in-place editing (`sed -i`, `perl -pi`, `awk -i inplace`) of ANY file, tracked or not.
- Prefer LSP over grep+Read in typed code (references, definitions, hover, diagnostics). Fall back to `rg` for plain text or unindexed file types.
- Verify CLI syntax with `--help` before guessing.
- WebSearch before writing config, CI, infra, or library-integration code wherever the feedback loop is slow or remote: official docs, then GitHub issues, then write. Local configs verifiable in seconds are exempt — just test them. If research would take >5 minutes, say so and ask.

## Quality Checks & Failure Budget

After any code change, run the project's quality checks (whatever its CLAUDE.md specifies) before declaring done; if unknown, check there or ask.

- Any other failing approach: max 3 attempts, then stop and ask.

## Tool Use Efficiency

- Run expensive commands once: long output → `/tmp/<name>.log`, then grep the file. Never re-run with different filters.
- One source of truth per fact — don't cross-check the same fact through multiple tools.
- Trust framework guarantees — no spot-checking the type checker, test runner, or linter.

## Engineering Judgment

1. **Match complexity to the problem.** Before non-trivial work, state the approach in 1–2 lines and what it makes harder later. No speculative flexibility; no painting into corners.
2. **Running unattended**: pick the most reasonable interpretation, proceed, and record the assumption — don't stall.
3. **Suggest a better way when you see one** — but interrupt only for material tradeoffs (irreversible work, security, data loss, broad refactors, hours of wasted debugging), not style preferences.
4. **Rank every suggestion by what it makes faster or better.** An unprompted proposal must name the efficiency gain (tokens, wall-clock, steps, human interruptions) or the output-quality gain it buys, and roughly how much. Correctness holes, missing instrumentation, and process-hygiene gaps are worth fixing when they're in the way — but they are not the headline, and never lead with them. If the best thing found is only a gap in coverage or bookkeeping, say the search found no gain and stop, rather than promoting the gap to fill the slot.

## Security

- Ansible Vault for any secrets that must be referenced — never inline them anywhere.

## Obsidian

- Vault: `~/vault`; templates: `~/vault/Templates`. Suggest a note when a key insight or decision surfaces.

## Maintaining These Rules

- Every line here costs attention in every session. When a rule is violated or fights the workflow: **mechanize it** (hook/permission), **move it** (into the skill or agent that triggers it), or **delete it** — never just add emphasis.
- Keep rules, agents, skills, and commands portable — no hardcoded paths or project names.
