# Research Questions

1. What hook events does `claude/.claude/settings.json` register (PreToolUse, PostToolUse, Notification, etc.), and what matcher/command pairs exist for each?
2. What shell scripts live under `claude/.claude/scripts/`, and for each, what does it check, what input does it read (stdin/env/args), and what exit codes or JSON output does it produce?
3. What is the stdin/stdout contract these gate scripts follow (e.g. hook JSON in, `permissionDecision` JSON or exit-2 out), and where is that contract documented or implemented?
4. What content exists in the root `claude/.claude/CLAUDE.md`-equivalent global rules file and the files under `claude/.claude/rules/`, and how is each rule currently expressed (prose instruction vs. enforced mechanism)?
5. What is the full content and structure of the agent definitions at `claude/.claude/agents/coder.md` and `claude/.claude/agents/coder-deep.md`, including any preloaded skills they reference?
6. What is the full content and structure of the agent definitions at `claude/.claude/agents/code-reviewer.md` (and related reviewer agents such as `code-reviewer-deep.md`), including their review criteria and output format?
7. What skill files do the coder and code-reviewer agents preload or reference (e.g. `coder-core`, `code-reviewer-memory`, `review`), and what logic in those skills currently relies on the agent reading and following written instructions?
8. Which existing scripts already mechanize a written rule (e.g. `bash-safety-gate`, `git-discipline-gate`, `review-commit-gate`, `spec-budget-gate.sh`, `comment-bloat-gate.sh`), and what pattern (regex matching a tool call, file-content linting, state-file tracking) does each use?
9. How do telemetry/logging scripts (e.g. `log-agent-usage.sh`, `log-skill-use.sh`, `log-escape`, `log-spec-run`) record agent and skill invocations, and what data format do they write to?
10. What test or verification patterns exist for these hook scripts (any test files, manual invocation examples, or self-check patterns embedded in the scripts)?
11. How does `claude/.claude/skills/review/log-review-finding` and other finding-log mechanisms (`claude/.claude/skills/_shared/finding-log.md`) structure and persist review output, and what parts are free-form prose versus structured fields?

## Exploration Map

- `claude/.claude/settings.json` — hook registration and permission configuration
- `claude/.claude/scripts/` — all gate/guard/log shell scripts and their I/O contracts
- `claude/.claude/rules/` and the global rules file — currently prose-only instructions
- `claude/.claude/agents/coder.md`, `coder-deep.md`, `code-reviewer.md`, `code-reviewer-deep.md` — target agent definitions
- `claude/.claude/skills/coder-core/`, `claude/.claude/skills/code-reviewer-memory/`, `claude/.claude/skills/review/` — skills these agents preload
- `claude/.claude/skills/_shared/finding-log.md` — shared logging/finding structure
