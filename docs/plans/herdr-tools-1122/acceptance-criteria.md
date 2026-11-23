# Acceptance Criteria — herdr-tools-1122

> Written before implementation. The closing Verify phase reconciles these
> against the test suite.

## Ticket criteria (verbatim)

### Lane resume script

- **AC1** — A script under scripts/tools/ writes each lane's brief, worktree, branch and session id to a durable file beside the worktree when the lane starts, and `herdr-lane-resume <name>` reopens the workspace, resumes the session and sends the brief from that file.
- **AC2** — A lane closed through the script leaves the lane list, so a monitor reading that list reports nothing for it.
- **AC3** — Tests under ~/dotfiles/tests/scripts/ cover a resume after the file exists and a close that removes the entry.

### Lane monitor

- **AC4** — A `lane-status` script prints low memory, scratch volume under a threshold, and each lane in the lane file whose agent_status is not working; a Monitor until-loop can call it with no sleep chain.
- **AC5** — Tests cover a closed lane absent from the output and a quota line present when df reports under the threshold.

### herdr-phase-change report-to

- **AC6** — A test runs herdr-phase-change with a slash-command prompt and checks the sent prompt names the sending session as the report-to target; it fails before the change.

### herdr-phase-change resolution

- **AC7** — A test passes a ListAgents-style session name and a worktree path; both resolve to the pane id. It fails before the change.

### Prune of merged lane worktrees

- **AC8** — One existing step (the lane merge line, or session start) runs the prune of merged, clean lane worktrees; no new hook process.
- **AC9** — After one run, the worktree count is the count of unmerged or dirty lanes.

### hunk-review-pane label

- **AC10** — hunk-review-pane renames its own pane (`$HERDR_PANE_ID`) to `review` at start. A test starts it with a stub herdr in an unlabeled pane and checks the rename call; it fails without the change.

### pull_keep_index built pages

- **AC11** — A test builds this state (staged built pages, a pull that changes the same pages) and the run ends with every local change back, staged files staged, and the pages rebuilt.
- **AC12** — --put-back on that save commit does the same.
- **AC13** — --help prints usage.

### pull_keep_index shared checkout

- **AC14** — A pull through pull_keep_index.py in a checkout where another session has uncommitted edits either leaves those files in the tree for the whole pull, or refuses and names the files and the way out.
- **AC15** — A put-back that fails never leaves the edits only in an unreferenced commit: it keeps a named ref and prints it.
- **AC16** — A test pins both, with a second writer changing a file during the pull.

## Plan-derived criteria (observable behavior the ticket implies)

- **AC17** — A lane file that is malformed or unreadable stops the lane tools with a message naming the file and the bad field, and never reads as an empty lane list.
- **AC18** — Starting a worktree without `--fork` does not create a lane entry, so lane-status never reports a popup worktree as a dead lane.
- **AC19** — After a phase change, resuming the lane sends the latest phase prompt and resumes the post-`/clear` session, not the original brief.
- **AC20** — A lane whose agent is gone is reported by lane-status as having no agent rather than being left out.
- **AC21** — A lane with an open entry is never removed by the prune, and when the lane list cannot be read the prune removes nothing and says why.
- **AC22** — A target naming a directory that holds several agents, or a session name with no pane, stops herdr-phase-change with a message and sends nothing.
- **AC23** — When no sending session can be named, herdr-phase-change sends nothing and says why.
- **AC24** — A failed hunk-review-pane rename warns naming the pane and the review still opens.
- **AC25** — Every message that names the saved changes also names their ref, and a successful put-back removes only its own ref and lists any older refs without deleting them.
- **AC26** — When the merge driver cannot rebuild a built page, pull_keep_index exits non-zero naming the page, the ref and the way out, with the saved changes still reachable.
- **AC27** — A shared, dirty checkout whose branch has local commits is refused with the dirty files named and nothing pulled or set aside.
- **AC28** — Two pull_keep_index runs in one repo never run their set-aside and put-back at the same time.
- **AC29** — The full test suite and lint pass, and the change pages are rebuilt with no stale reference to a removed name.
- **AC32** — `herdr-lane-resume --close` closes the lane's herdr workspace before it removes the entry and prunes, and refuses with nothing changed while a claude agent inside the worktree is working. (P3.1, lane session, 2026-11-22)

## Manual only

- **AC30** — lane-status reads memory correctly on macOS.
  No automated test runs on a Mac here; the `vm_stat` path is checked by hand on a Mac before the item closes.
- **AC31** — pull_keep_index rebuilds built pages through the real merge driver on a clone of this repo.
  Tests use a stub driver; the real driver is run once by hand and its output recorded.
