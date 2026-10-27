---
type: "Change"
title: "A dirty commit is denied with a /review reason instead of a prompt"
description: "`review-commit-gate` denies a `git commit` while coder work from the session has no converged review. The reason tells the session to run /review and commit after it converges. A docs-only commit chain that ends in `git rev-parse` now passes. An internal error in the gate still asks."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-23T20:40:16-05:00"}
seq: 7
kind: "behavior"
components: ["script/review-commit-gate"]
evidence: ["work incident", "tests"]
watches: []
---

## Change

- **Dirty commit:** the gate denies the commit, in place of a permission prompt. The reason tells the session to run /review on the coder work and commit after it converges. It also names the plain form that the docs-only pass accepts: a `git commit` from the repo root, in its own Bash call, with no `cd`, `env` or `git -C`.
- **rev-parse:** `git rev-parse` joins the read-only git subcommands next to status, diff, log and show. The `--output` and redirect checks apply to it.
- **Kept:** an internal error in the gate still asks. A deny there blocks every Bash call in every session while the hook is broken.
- **Override:** the user commits by hand with `! git commit`. The hook does not run on `!` commands. This replaces the one-click Yes on the prompt.

## Evidence

Work incident: four unattended agent-ledger sessions stopped on the Yes/No prompt and waited for the user. One of them was a docs-only commit that ended in `git rev-parse HEAD`, which the docs-only pass did not accept. Tests: the gate test file passes on the new script (76 tests). Against the installed script, every dirty-commit test and the four new tests fail, and the internal-error tests pass.

## Result

Ready to install. A session that commits unreviewed coder work now runs /review by itself, and the user gets no prompt. This reverses the earlier change that made the gate ask, for the dirty-commit case only.

## Watch

None. No intake metric counts permission prompts from this gate.

## Back-out

Restore `review-commit-gate.py` and `test_review_commit_gate.py` from the dotfiles history.
