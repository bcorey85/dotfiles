# Global Claude Code Rules

## Precedence

When rules conflict: the user's current instruction > project CLAUDE.md > this file > skill/agent defaults. A project file may relax a global rule only through a mechanism this file names (e.g., direct-edit repos).

## Safety Rails (hook-enforced — never work around a block)

`bash-safety-gate`, `git-discipline-gate`, `review-commit-gate`, `shell-write-gate`, `block-credential-read`, and `write-edit-safety-gate` deterministically block: SSH/scp/rsync, credential reads (any `.env*` or `*.key` file, including via `cat`), inline interpreters (`python3 -c`, `node -e` — write a script file and run it), `sh -c`/`bash -c`, `rm -rf`, `xargs`, `find -exec`, sudo, force-push, commit/push on main (exempt: direct-edit repos), `git stash`, `git commit --amend`, destructive resets, pipe-to-shell, shell writes to tracked files or (for coders) test files, and `git commit` after an unreviewed coder dispatch. omp (Oh My Pi) consumes these same scripts via the `omp` stow package's `claude-security-bridge.ts` — preserve their stdin/stdout contract (hook JSON in; `permissionDecision` JSON or exit-2 out) when editing or regenerating. When a gate blocks you: report it to the user and stop — never rephrase a command to slip past. The gates regex the full command string, so false positives happen; a block is a report, not a retry puzzle.

Workflow gates (advisory, not rails — their deny message says what to do next, and each has a narrow escape you append to the command as a comment, on the user's say-so): shell-write-gate (`#skip-shell-write-gate`; never disarms its test-ownership check), quality-check-cap (`#skip-quality-cap`).

## Where the rest lives

Orchestration, tool use, working judgment, git conventions, Obsidian and rule maintenance live in `~/.claude/orchestration.md`, injected at session start. Main session only — subagents never receive it.

Prose style lives in the `Laconic` output style (`~/.claude/output-styles/laconic.md`). Main session only.

Never add attribution or session trailers to commits or PRs.

## Quality Checks & Failure Budget

After a code change, run only the tests and fast checks for the files you changed. Run the full suite and long quality gates (whatever the project's CLAUDE.md specifies) once per phase, at the end of review — never after each edit, and never inside a coder, test-writer or reviewer dispatch. Outside a review loop, run them once before declaring done. If the checks are unknown, look in the project's CLAUDE.md or ask.

- Any other failing approach: max 3 attempts, then stop and ask.

## Compact instructions

When you compact, keep decisions with their reasons, every measured number, open items in order, commit hashes, file paths, and the rules that bind the next step. Drop tool output and narrative.

## Engineering Judgment

- **Name for intent, not shape.** Names say what a value is in the domain: `seededTimekeepers`, not `keeperRows`; `timekeeper`, not `k` or `t`; `transaction`, not `tx`. Reading a longer name costs less than decoding a short one. Single letters only for loop indexes.

## Security

- Ansible Vault for any secrets that must be referenced — never inline them anywhere.
