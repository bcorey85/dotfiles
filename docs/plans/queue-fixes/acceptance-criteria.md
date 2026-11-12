# Acceptance criteria

- AC1: A Bash command whose only pipe characters are a `||` operator is never denied by `pipe_shell_check.py` as pipe-to-shell.
- AC2: A real pipe into a shell (`| bash`, `|& sh`) is still denied by `pipe_shell_check.py`.
- AC3: `pull_keep_index.py` on a branch with no upstream and no remote branch exits 0 and leaves staged files staged, so a chained `git push -u` runs.
- AC4: `pull_keep_index.py` on a branch with no upstream whose remote branch exists pulls that branch and keeps staged files staged.
- AC5: `bash tests/run.sh` passes from the checkout.
