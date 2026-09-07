---
name: commit
disable-model-invocation: true
description: Draft a commit message from the STAGED changes, then commit and push. Use when the user says "commit", "commit and push", or "ship this" — the user stages; this skill never runs `git add`.
allowed-tools: [Bash]
---

# Commit

Commit staged changes and push. NOT complete until push succeeds (or `+no-push`). No approval pauses — one pass.

The USER stages; Claude NEVER stages (contract-staged files, e.g. task-dir removals, arrive staged — expected). Message from staged diff only.

Use `JIRAPROJECT-TICKETNUMBER: description` if the branch has a ticket key, otherwise use conventional commits (`type(scope): description`).

**First commit on a branch matches the branch slug verbatim.** Later commits describe their own change.

## Modifiers

- `+no-push` — Skip the push to remote after committing. By default, `/commit` pushes to the tracking remote after a successful commit.
- `+no-escape` — Skip the review-flywheel escape check (step 9). Use for commits you know aren't fixes to already-reviewed code.

## Instructions

1. **Branch guard**: main or master means STOP — create a branch first, re-run. Never commit to main or master, even staged.
2. Staged diff stat plus status short.
3. **Nothing staged** means tell the user to add first, then re-run. Stop.
4. **Unstaged or untracked beyond staged** means note briefly, never stage.
5. Draft a commit message from the staged diff.
6. **Secret scan (blocking)**: run `git diff --cached -G'(AKIA[0-9A-Z]{16}|BEGIN (RSA|EC|OPENSSH|DSA|PGP) PRIVATE KEY|ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35})' --name-only`. Any file listed → STOP: name the files (never echo the matched values), tell the user to move the secret out (Ansible Vault for anything that must be referenced), and do not commit. If `gitleaks` is installed, prefer its staged-changes scan instead (verify the subcommand with `gitleaks --help`).
7. Create the commit. Use a HEREDOC for the message so multi-line bodies and special characters survive: `git commit -m "$(cat <<'EOF' ... EOF)"`.
8. **Push** (skip on `+no-push` or worktree branches — merged by parent, never pushed). If no upstream is set, push with upstream configured. Failure means report clearly, never force-push.
9. **Escape check (silent, non-blocking).** One conservative judgment: does this commit fix a defect in branch-loop-blessed code (corrects already-committed branch work — not first commit, net-new, or requirement change)? Only when confident, log one line per defect (no prompt):

   ```bash
   bash ~/.claude/scripts/log-escape repo="$(basename "$(git rev-parse --show-toplevel)")" stage_found=pr-human gate_missed=review class=<bug|smell|duplication|test-gap|other> severity=<high|medium|low> guard=<...> desc="<one line>" file=<representative path>
   ```

   `guard` from `~/.claude/skills/_shared/escape-ratchet.md`, picked without pausing; name it in step 10 (commit landed — guard is follow-up, not blocker).

   Skip silently when the commit is net-new work, a first commit, a requirement change, or you're unsure. `+no-escape` disables this step entirely.

10. Report commit hash, branch, push result. Never end unconfirmed.

## Arguments

$ARGUMENTS
