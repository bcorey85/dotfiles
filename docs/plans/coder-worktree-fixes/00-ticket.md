# Coder and worktree fixes

Four agent-evals queue items; each paragraph is the item's Done-when clause or Fix line as written.

## forked-worktree-workspace-closes-about-a-minute

A `--fork` run leaves the workspace open with the fork working. If it does close, the script or a doc names the
recovery steps above (`herdr worktree open --cwd <main checkout> --path <worktree> --focus`, then
`herdr-dev <worktree> <ws> <fork session id> <prompt>`).

## review-coder-deletes-untracked-files-it-did-not

Fix: the coder brief says to put one-off scripts in the scratchpad, never in the repo tree, and to never delete a file
it did not create.

## review-class-closure-sweeps-readers-without

Class closure checks what each member reads the value for before converting it, and lists members it leaves alone
with the reason, so a later round does not undo it.

## worktree-rule-reads-as-an-order-to-create

The rule opens with: create a worktree only when the user explicitly asks for one; "make a branch" means git checkout
-b in the current checkout. The location and herdr steps apply only after that.
