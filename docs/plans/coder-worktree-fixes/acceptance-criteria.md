# Acceptance criteria: coder and worktree fixes

From the queue items' Done-when clauses.

## forked-worktree-workspace-closes-about-a-minute

- AC1: A `herdr-worktree --fork` run that succeeds starts a watcher that checks the new workspace about two minutes
  later.
- AC2: When the workspace is gone, the watcher writes the recovery steps with literal values to a log in the
  worktree's git dir and shows a herdr notification: `herdr worktree open --cwd <main checkout> --path <worktree>
  --focus`, then `herdr-dev <worktree> <ws> <fork session id> <prompt>`.
- AC3: `herdr-worktree --help` names the same recovery steps.

## review-coder-deletes-untracked-files-it-did-not

- AC4: coder-core tells coders to write one-off scripts in the scratchpad, never in the repo tree.
- AC5: coder-core tells coders never to delete an untracked file they did not create.

## review-class-closure-sweeps-readers-without

- AC6: The class-closure prompt checks what each member reads the value for before it calls the member open.
- AC7: The closure receipt names each member left alone and the reason.

## worktree-rule-reads-as-an-order-to-create

- AC8: The orchestration.md worktree bullet opens with: create a worktree only when the user explicitly asks for
  one; "make a branch" means `git checkout -b` in the current checkout. The location and herdr steps come after.
