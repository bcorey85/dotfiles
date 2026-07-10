---
name: commit
description: Draft a commit message from the STAGED changes, then commit and push. Use when the user says "commit", "commit and push", or "ship this" — the user stages; this skill never runs `git add`.
allowed-tools: [Bash]
---

# Commit

Commit staged changes and push to remote. This skill is NOT complete until the push succeeds (or `+no-push` is active). Do NOT stop to ask for approval — execute the full pipeline in one pass.

The USER is responsible for staging files. Claude NEVER stages files. (Sole exception: skills whose documented contract includes staging — e.g. `/finalize`'s `git rm` of task-directory files — may arrive here with those files already staged; that's expected, not a violation.) Draft the commit message from staged changes only (`git diff --cached`), then commit and push.

Use `JIRAPROJECT-TICKETNUMBER: description` if the branch has a ticket key, otherwise use conventional commits (`type(scope): description`).

**First commit on a branch must match the branch slug verbatim.** If the branch is `IQ-402-extract-shared-constants` and there are no prior commits on the branch (check with `git log <base>..HEAD --oneline`), the commit message must be `IQ-402: extract shared constants` — same ticket key, same description words, same order. Subsequent commits on the branch describe what changed in that specific commit and do not need to match the branch name.

## Modifiers

- `+no-push` — Skip the push to remote after committing. By default, `/commit` pushes to the tracking remote after a successful commit.
- `+no-escape` — Skip the review-flywheel escape check (step 9). Use for commits you know aren't fixes to already-reviewed code.

## Instructions

Execute all steps in a single pass — do NOT pause for user approval between steps.

1. **Branch guard**: Run `git branch --show-current`. If the branch is `main` or `master`, STOP: "Refusing to commit directly to `<branch>`. Create a branch first (`/create-branch`) and re-run `/commit`." Never commit or push to main/master, even if changes are already staged.
2. Run `git diff --cached --stat` to see what's staged. Also run `git status --short` to check for unstaged/untracked changes.
3. **If nothing is staged**: Tell the user "Nothing staged. Stage your changes with `git add` first, then re-run `/commit`." Stop here.
4. **If there are unstaged or untracked changes** beyond what's staged: Briefly note them (e.g., "FYI: 3 unstaged files not included in this commit: [list]"). Do NOT stage them — just inform.
5. Draft a commit message from the staged diff.
6. **Secret scan (blocking)**: run `git diff --cached -G'(AKIA[0-9A-Z]{16}|BEGIN (RSA|EC|OPENSSH|DSA|PGP) PRIVATE KEY|ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35})' --name-only`. Any file listed → STOP: name the files (never echo the matched values), tell the user to move the secret out (Ansible Vault for anything that must be referenced), and do not commit. If `gitleaks` is installed, prefer its staged-changes scan instead (verify the subcommand with `gitleaks --help`).
7. Create the commit. Use a HEREDOC for the message so multi-line bodies and special characters survive: `git commit -m "$(cat <<'EOF' ... EOF)"`.
8. **Push to remote** (unless `+no-push` was passed or on a worktree branch): Check the branch name with `git branch --show-current`. If the branch starts with `worktree-`, skip pushing — worktree branches are merged by the parent session, not pushed directly. Otherwise, run `git push`. If no upstream is set, use `git push -u origin <branch>`. If the push fails for any reason (auth, diverged history, network), report the error clearly — do NOT retry with `--force` or destructive flags.
9. **Escape check (silent, non-blocking — feeds the review flywheel).** Make one conservative judgment: does this commit _fix a defect in code that this branch's `/code`+`/review` loop already blessed_? That means the staged diff corrects already-committed branch work (not a first commit, not net-new code, not a changed requirement) — a bug or smell a human caught after the gates passed it. This is ground truth for `/review-stats`. Only when you are confident that's what happened, log one line per distinct defect (no user prompt, do not pause):

   ```bash
   bash ~/.claude/scripts/log-escape repo="$(basename "$(git rev-parse --show-toplevel)")" stage_found=pr-human gate_missed=review class=<bug|smell|duplication|test-gap|other> severity=<high|medium|low> desc="<one line>" file=<representative path>
   ```

   Skip silently when the commit is net-new work, a first commit, a requirement change, or you're unsure — a mislabeled escape pollutes the data. `+no-escape` disables this step entirely.

10. **Confirm completion**: Report the commit hash, branch name, and push result (or "push skipped — worktree branch"). Do NOT end without confirming the commit succeeded.

## Arguments

$ARGUMENTS
