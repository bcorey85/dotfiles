# Global Claude Code Rules

## Communication

- Never paste secrets — give me the command to run.
- Verify CLI syntax with `--help` before guessing.
- Be concise. Reference code with `file_path:line_number`.
- When a task spans >3 files or >1 service, propose a plan before writing code.

## Behavior

- **MANDATORY: Never code directly. Always delegate to the `/code` subagents** (`backend-coder`, `frontend-coder`, or `backend-architect` / `frontend-architect` first when design decisions are needed). The main agent's role is briefing, reviewing, and orchestration — not editing files. The only exceptions are trivial single-line edits explicitly requested by the user (e.g., "change this variable name") or repository configuration files like `CLAUDE.md` itself.
- Don't over-engineer. Only change what's requested. Don't refactor unrelated code while implementing a feature.
- Never hardcode paths or project names in rules, agents, skills, or commands — keep portable.
- DO NOT GIT STASH UNLESS YOU HAVE EXPLICIT PERMISSION FROM THE USER. Stashing causes critical failures in parallel agent work and also resets staged files.
- **MANDATORY: WebSearch before writing any config, CI, infra, or library integration code.**
  Before writing Docker configs, CI pipelines, tool configs (Playwright, Vite, ESLint, etc.), or any code that touches external tool behavior:
  1. Search the tool's official docs for the specific feature/environment
  2. Search GitHub issues if the docs don't answer it
  3. Only then write the code
     This is NOT optional. Do NOT write config changes based on reasoning alone. Every CI/infra guess costs 5-10 minutes of pipeline time.
     If research would take >5 minutes, say so and ask for direction instead.
- Maximum 3 attempts on any failing approach. After 3, stop, document what failed, and ask for direction.
- Save all Playwright screenshots to `/tmp/`, never inside a project repo.
- **NEVER use Bash to write files.** This is non-negotiable:
  - Create/overwrite files → **Write tool** (not `cat <<`, `echo >`, heredocs)
  - Edit files → **Edit tool** (not `sed`, `awk`)
- Prefer **Read tool** with offset/limit over `cat`, `head`, `tail` for reading files.
- Prefer `rg` over `grep` and `fd` over `find` when available.
- **Every `Agent` call MUST set `model` explicitly — UNLESS the agent's own frontmatter defines a `model`.** When the agent file pins a model (e.g. `backend-architect` / `frontend-architect` pin `model: opus`), do NOT pass a call-site `model`: a call-site model _overrides_ the frontmatter and would silently downgrade an Opus-pinned agent. Omit `model` entirely and let the frontmatter win. The `agent-model-guard` PreToolUse hook (`~/.claude/scripts/agent-model-guard.sh`) already allows an empty call-site model when the agent frontmatter has a `model:` line; it rejects an _unpinned_ agent dispatched with no model. So: frontmatter-pinned agent → omit model; everything else → set model explicitly.
  - `model: "haiku"` — read-only / lookup work (research, fact extraction, "where is X", file surveys). This is the default for QRSPI research and tactical lookups.
  - `model: "sonnet"` — fan-out implementation, code edits, multi-file analysis, code review.
  - `model: "opus"` — **never from the call site.** The hook rejects `model: "opus"`. Opus is reserved for the main orchestrator. The only way a subagent runs on Opus is its own frontmatter pin — which you honor by _omitting_ the call-site model, never by overriding to a smaller model.
  - Pair with `subagent_type` deliberately: `Explore` (read-only lookup, default for research), `general-purpose` (multi-file tracing Explore can't handle), `backend-coder` / `frontend-coder` / `*-architect` / `code-reviewer` per their descriptions.
- **Prefer LSP over grep+Read for typed code.** When working in a project with a language server (TypeScript, Python with pyright, Go, Rust, etc.), use the LSP tool for: finding references, go-to-definition, hover/type info, and diagnostics. One LSP call replaces 5–10 grep+Read pairs. Reach for it on refactors, signature changes, import rewrites, "find every usage of X", and post-edit type checks. Fall back to `rg` only for plain text or unindexed file types.

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

@RTK.md
