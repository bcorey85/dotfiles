# Global OpenCode Rules

## Communication

- Never paste secrets — give me the command to run.
- Verify CLI syntax with `--help` before guessing.
- Be concise. Reference code with `file_path:line_number`.
- When a task spans >3 files or >1 service, propose a plan before writing code.

## Behavior

- **MANDATORY: Never code directly. Always delegate to the `/code` subagents** (`backend-coder`, `frontend-coder`, `coder` for non-web repos, or `backend-architect` / `frontend-architect` first when design decisions are needed). The main agent's role is briefing, reviewing, and orchestration — not editing files. Exceptions: trivial single-line edits explicitly requested by the user (e.g., "change this variable name"), repository configuration files like `AGENTS.md` itself, and repos whose project `AGENTS.md` declares itself a **direct-edit repo** (dotfiles, config-only, personal scripts) — there, edit directly.
- **MANDATORY: A coder dispatch obligates a `/review` before `/commit` — no exceptions for how it was dispatched.** The `/code` skill chains review automatically; a **raw `Task` call to a coder (`backend-coder`/`frontend-coder`/`coder`, incl. `-deep`) does NOT** — so when you dispatch a coder directly, you MUST invoke `/review` yourself once it returns, before committing. Prefer `/code` precisely because it wires this up. The ONLY skip is a genuinely trivial change (typo, single-line, rename, comment-only). "I'll review later" / "it looks fine" / "the coder said it passes" are not exemptions. If you're about to `/commit` and no `/review` ran this session on the current changes, stop and run it first.
- Don't over-engineer. Only change what's requested. Don't refactor unrelated code while implementing a feature.
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
- **Models are configured per-agent** in `~/.config/opencode/agents/` frontmatter. Don't override models at dispatch time — the frontmatter pin wins.
- **Prefer LSP over grep+Read for typed code.** When working in a project with a language server (TypeScript, Python with pyright, Go, Rust, etc.), use the LSP tool for: finding references, go-to-definition, hover/type info, and diagnostics. One LSP call replaces 5–10 grep+Read pairs. Reach for it on refactors, signature changes, import rewrites, "find every usage of X", and post-edit type checks. Fall back to `rg` only for plain text or unindexed file types.

## Quality Checks

After any code change, run the project's quality checks (validate, lint, typecheck, tests, build, format — whatever `AGENTS.md` specifies) before declaring done. If unknown, check the project `AGENTS.md` or ask.

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
