---
type: "Change"
change_type: "added"
title: "herdr-worktree-prune lists and removes merged, clean lane worktrees"
description: "A new command beside herdr-worktree lists the finished lane worktrees of a repo and, with --apply, removes each with git worktree remove and then deletes its branch with git update-ref -d on the checked commit; --branches does the same for merged branches that have no worktree."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-15T15:12:56-06:00"}
seq: 7
kind: "fix"
components: ["script/herdr-worktree-prune"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_herdr_worktree_prune.py::RemovalTest::test_a_merged_clean_worktree_is_listed_and_apply_removes_it_and_its_local_branch"
asked: ""
proof: []
unmeasured: "No intake number reads disk use or worktree count; the list mode prints both on demand."
---

## Change

`herdr-worktree` makes one sibling worktree per lane and nothing removed them: `~/dotfiles` held 213 lane worktrees
and 226 merged local branches. `scripts/.local/bin/herdr-worktree-prune` is a command the user runs by hand, in any
repo, from the main checkout or a linked worktree.

- No option: it lists. One `remove` line per worktree it would remove (path, branch, size), one `keep` line per kept
  worktree with one reason, then totals. It removes nothing. It does run `git fetch origin <default branch>` first.
- `--apply`: it removes the listed worktrees with `git worktree remove` (never `--force`) and then deletes the
  branch with `git update-ref -d` on the commit it just checked as an ancestor of `origin/<default>`, never forced:
  git refuses when the tip moved in between. Plain `git branch -d` would refuse a branch whose tip is ahead of its own
  upstream, so the list line says "ahead of its own remote branch". Every condition is checked again for each tree
  right before its removal. One failure is reported and the rest go on; exit 1 when any step failed. The remote
  branch stays.
- `--branches`: the same list, or with `--apply` the same delete, for merged local branches that no worktree entry
  has checked out. Never the default branch, and never a branch that a worktree holds in a rebase or a bisect.

A worktree goes only when all of these hold: it is linked (not the main checkout, not the one the command runs from);
its folder exists; it is not locked, detached or bare; its branch is not the default branch and its tip is an ancestor
of `origin/<default>` after the fetch; `git status` is clean (ignored files do not count); it holds no submodule and
no ignored nested repo; no stash entry was made on its branch; no live process has its working directory inside it;
no herdr workspace or agent is on it. With no origin, no `origin/HEAD` or a failed fetch the command stops and removes
nothing. It never touches `refs/review-snapshots`, and never runs `git gc`, `git worktree prune` or `git stash drop`.

Three things a reader does not expect:

- A branch merged by squash or rebase is not an ancestor, so its tree is kept; the line says so.
- Plain `git worktree remove` deletes ignored files with the folder (pinned by a test). In `agent-ledger-dev` that is
  each lane's `target/` build folder, 15 GB in the one measured.
- A lane that was made and never committed to counts as merged. It goes when it is clean and nothing runs in it.

## Evidence

judgment: the queue item `dotfiles-holds-213-lane-worktrees-and-226-merged` counted the trees; only
`peer-review/SKILL.md` and `review/full_check.py` removed a worktree, each its own temporary one.

## Result

`tests/scripts/test_herdr_worktree_prune.py` holds 71 tests on throwaway repos with a local bare origin (8.6 s). Not
checked: real `lsof` and `du` output on macOS (the `lsof` path is tested with a stub), and a run on Python 3.9, the
stock macOS version: the script is written for it, and this machine has only 3.14.

List mode on 2026-11-15, nothing removed:

| Repo | Would remove | Bytes | Kept | Kept by reason | Merged branches without a worktree |
| --- | --- | --- | --- | --- | --- |
| `~/dotfiles` | 190 | 3,230,584,832 | 36 | 13 uncommitted changes, 10 process running, 9 not merged, 2 detached, 1 stash entry, 1 main checkout | 21 |
| `~/agent-evals` | 0 | 0 | 27 | 25 not merged, 1 folder gone, 1 main checkout | 0 |
| `~/agent-ledger-dev` | 18 | 120,499,408,896 | 12 | 8 not merged, 3 detached, 1 main checkout | 19 |

Listed branches that are ahead of their own remote branch but fully on the default branch, which plain
`git branch -d` would refuse: 21 in `~/dotfiles` (18 with a worktree, 3 without) and 15 in `~/agent-ledger-dev` (4 and
11).

The queue item's own counts for `~/dotfiles`, taken again on 2026-11-15 after the command was written. Nothing was
removed, so no count fell; each rose because lanes kept opening during the day.

| Count | Queue item | After the change |
| --- | --- | --- |
| `git worktree list` entries | 214 | 226 |
| local branches | 236 | 248 |
| local branches merged (item: into `master`; after: into `origin/master`) | 226 | 236 |
| `refs/review-snapshots` refs | 9,348 | 10,322 |
| loose objects | 38,216 (459.04 MiB) | 40,906 (492.88 MiB) |
| packs | 22 (21.69 MiB) | 22 (21.69 MiB) |

The counts fall only when the user runs `--apply`. The command leaves the snapshot refs and the loose objects alone.

`~/agent-evals` compares with `origin/master` while its lanes merge into `bench-base`, so every lane there reads as
not merged and is kept.

## Watch

None: a command run by hand that prints its own counts.

## Back-out

Revert the commit. Removed worktrees do not come back; their branches stay on origin.
