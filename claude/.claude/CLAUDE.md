# Global Claude Code Rules

## Communication

- Never paste secrets — give me the command to run.
- Verify CLI syntax with `--help` before guessing.
- Be concise. Reference code with `file_path:line_number`.
- When a task spans >3 files or >1 service, propose a plan before writing code.

## Behavior

- **MANDATORY: Never code directly. Always delegate to the `/code` subagents** (`backend-coder`, `frontend-coder`, `coder` for non-web repos, or `backend-architect` / `frontend-architect` first when design decisions are needed). The main agent's role is briefing, reviewing, and orchestration — not editing files. Exceptions: trivial single-line edits explicitly requested by the user (e.g., "change this variable name"), repository configuration files like `CLAUDE.md` itself, and repos whose project CLAUDE.md declares itself a **direct-edit repo** (dotfiles, config-only, personal scripts) — there, edit directly.
- **MANDATORY: A coder dispatch obligates a `/review` before `/commit` — no exceptions for how it was dispatched.** The `/code` skill chains review automatically; a **raw `Agent` call to a coder (`backend-coder`/`frontend-coder`/`coder`, incl. `-deep`) does NOT** — so when you dispatch a coder directly, you MUST invoke `/review` yourself once it returns, before committing. Prefer `/code` precisely because it wires this up. The ONLY skip is a genuinely trivial change (typo, single-line, rename, comment-only). "I'll review later" / "it looks fine" / "the coder said it passes" are not exemptions. If you're about to `/commit` and no `/review` ran this session on the current changes, stop and run it first.
- Never hardcode paths or project names in rules, agents, skills, or commands — keep portable.
- DO NOT GIT STASH UNLESS YOU HAVE EXPLICIT PERMISSION FROM THE USER. Stashing causes critical failures in parallel agent work and also resets staged files.
- **MANDATORY: WebSearch before writing any config, CI, infra, or library integration code.**
  Before writing Docker configs, CI pipelines, tool configs (Playwright, Vite, ESLint, etc.), or any code that touches external tool behavior:
  1. Search the tool's official docs for the specific feature/environment
  2. Search GitHub issues if the docs don't answer it
  3. Only then write the code
     This is NOT optional. Do NOT write config changes based on reasoning alone. Every CI/infra guess costs 5-10 minutes of pipeline time.
     Scope: this applies when the feedback loop is slow or remote (CI pipelines, Docker builds, deployed infra, configs that only fail at build/run time). Local configs verifiable in seconds (shell aliases, tmux binds, editor settings) are exempt — just test them.
     If research would take >5 minutes, say so and ask for direction instead.
- Maximum 3 attempts on any failing approach. After 3, stop, document what failed, and ask for direction.
- Save all Playwright screenshots to `/tmp/`, never inside a project repo.
- **NEVER use Bash to write files.** This is non-negotiable:
  - Create/overwrite files → **Write tool** (not `cat <<`, `echo >`, heredocs)
  - Edit files → **Edit tool** (not `sed`, `awk`)
- Prefer **Read tool** with offset/limit over `cat`, `head`, `tail` for reading files.
- Prefer `rg` over `grep` and `fd` over `find` when available.
- When the **context-mode plugin** is active, its `ctx_*` tools take precedence over the Read/`rg` preferences above for bulk read-only analysis; Read remains correct for files you're about to edit.
- **Agent-call model discipline** (enforced by the `agent-model-guard` PreToolUse hook, `~/.claude/scripts/agent-model-guard.sh`):
  - **Frontmatter-pinned agent → omit `model` at the call site.** A call-site model _overrides_ the pin and silently downgrades Opus-pinned agents (`backend-architect`, `frontend-architect`, `test-reviewer`, `ux-research-analyst`, `product-spec-manager`, and the `-deep` wrappers). This covers EVERY agent file with a `model:` line — when in doubt, check the frontmatter before dispatching.
  - **Unpinned agent → set `model` explicitly.** `haiku` for read-only/lookup work (research, fact extraction, "where is X", file surveys, QRSPI fan-out lookups); `sonnet` for implementation, code edits, multi-file analysis, code review.
  - **Never `opus`, `fable`, or `inherit` at the call site** — the hook rejects all three. Opus is reserved for the main orchestrator and runs in subagents only via a frontmatter pin (`+deep` dispatches the Opus-pinned `-deep` wrappers with `model` omitted). Fable costs more than Opus and is never a subagent model. A _deliberate_ call-site downgrade of a pinned agent (e.g. `+fast` passing `haiku` to a sonnet-pinned coder) is allowed.
  - Pair with `subagent_type` deliberately: `Explore` (read-only lookup, default for research), `general-purpose` (multi-file tracing Explore can't handle), coders / architects / reviewers per their descriptions.
- **Prefer LSP over grep+Read for typed code.** When working in a project with a language server (TypeScript, Python with pyright, Go, Rust, etc.), use the LSP tool for: finding references, go-to-definition, hover/type info, and diagnostics. One LSP call replaces 5–10 grep+Read pairs. Reach for it on refactors, signature changes, import rewrites, "find every usage of X", and post-edit type checks. Fall back to `rg` only for plain text or unindexed file types.

## Engineering Judgment

1. **Ask, don't assume.** If something is unclear, ask before writing a single line. Never make silent assumptions about intent, architecture, or requirements. When running unattended, pick the most reasonable interpretation, proceed, and record the assumption rather than blocking.
2. **Match solution complexity to the problem** — simplest solution for simple problems, better solutions for harder ones. Before a non-trivial implementation, state the approach in 1–2 lines and what it makes harder later. Don't over-engineer or add flexibility that isn't needed yet; don't paint into a corner either.
3. **Don't touch unrelated code** — only change what's requested. But do surface bad code or design smells you discover so we can address them as a separate issue.
4. **Flag uncertainty explicitly.** If you're unsure about something, see rule 1. Where it makes sense, run a small, localized, low-risk experiment and bring the hypothesis and results back to discuss. Confidence without certainty causes more damage than admitting a gap.
5. **Suggest a better way when you see one** — favor approaches with long-lasting impact over tactical fixes. But interrupt only for material tradeoffs (irreversible work, security, data loss, broad refactors, hours of wasted debugging), not style preferences.

## Quality Checks

After any code change, run the project's quality checks (validate, lint, typecheck, tests, build, format — whatever CLAUDE.md specifies) before declaring done. If unknown, check the project CLAUDE.md or ask.

- **Hard cap: run any single quality-check command at most TWICE per task.** Applies to every check — validate, linters, type checkers, test runners, builds, formatters.
- If exit code is 0, you're done with that check.
- If non-zero, redirect output to `/tmp/check.log`, read the full log, and fix **every reported failure in a single batch** before re-running. Do not re-run to inspect different parts of the same output — grep the log.
- If the second run still fails, **stop**. Document what's failing and ask for direction. Do NOT enter a fix-rerun-fix-rerun loop. That single anti-pattern is the largest source of runaway tool use.

## Tool Use Efficiency

You're paying real time and tokens for every tool call. Be deliberate.

- **Run expensive commands once.** If you need to inspect different parts of a long-running command's output (test runs, builds), redirect to `/tmp/<name>.log` and grep the file. Never re-run the same command with different filters or to a different `tail`/`head`.
- **One source of truth per fact.** Look up a package version, config value, or symbol location once and trust it. Don't cross-check the same fact through multiple tools.
- **Parallel ≠ better.** Parallel tool calls are for _independent_ questions. Multiple calls answering the same question are wasted, even when concurrent.
- **Read before grep.** If you already know the file path, just read the file. Don't grep for a symbol whose location you already have.
- **Trust framework guarantees.** The build tool, test runner, type checker, ORM, and linter do their jobs. Don't verify their output via separate spot checks.

## Git

- Never commit directly to main/master. Work on a feature branch.
- Don't amend or force-push commits unless explicitly asked.
- Keep diffs focused — one logical change per task.

## Security

- NEVER SSH into remote servers (ssh, scp, rsync to remote hosts).
- NEVER read or cat credential/secret files.
- Use Ansible Vault for any secrets that need to be referenced.

## Obsidian

- Note vault: `~/vault`. Templates: `~/vault/Templates`.
- Suggest a note when a key insight or decision comes up.
