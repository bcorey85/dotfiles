# herdr lane tooling: eight queued fixes

Eight queue items, each copied verbatim below. The Done-when lines of each are the acceptance criteria.

---

# herdr lane resume script keeps each lane's brief and session id in a durable file

Source: ~/agent-evals/queue/herdr-lane-resume-script-keeps-each-lane-s-brief.md

---
type: "QueueItem"
title: "herdr lane resume script keeps each lane's brief and session id in a durable file"
description: "A dead lane restarts in one command instead of a hand-rebuilt brief and three herdr calls."
generated: {"by": "claude-code/claude-fable-5-1", "at": "2026-11-22T14:40:12-06:00"}
kind: "chore"
status: "running"
rank: 1011
blocked_by: []
source: "claude/.claude/scripts/tools/herdr-worktree"
components: ["method/protocol"]
---

## Context
Session a0b58526 (2026-11-22): all three lanes died twice (OOM reboot at 11:48, an unexplained workspace close at 12:54). The reboot wiped the scratchpad briefs. Each restart was a rewritten brief plus herdr worktree open, agent start --resume and agent prompt per lane, and the Monitor loop kept firing "lane-rigs: gone" four times after that lane was closed on purpose. Adds to the 2026-11-10 change that logs recovery steps when a forked workspace closes.

## Done when
- A script under scripts/tools/ writes each lane's brief, worktree, branch and session id to a durable file beside the worktree when the lane starts, and `herdr-lane-resume <name>` reopens the workspace, resumes the session and sends the brief from that file.
- A lane closed through the script leaves the lane list, so a monitor reading that list reports nothing for it.
- Tests under ~/dotfiles/tests/scripts/ cover a resume after the file exists and a close that removes the entry.

---

# lane monitor reads the live lane list from a file and the scratch volume quota

Source: ~/agent-evals/queue/lane-monitor-reads-the-live-lane-list-from-a-file.md

---
type: "QueueItem"
title: "lane monitor reads the live lane list from a file and the scratch volume quota"
description: "One monitor command covers memory, scratch quota and only the lanes still open."
generated: {"by": "claude-code/claude-fable-5-1", "at": "2026-11-22T14:40:14-06:00"}
kind: "chore"
status: "running"
rank: 1011
blocked_by: []
source: "claude/.claude/scripts/tools/herdr-worktree"
components: ["method/protocol"]
---

## Context
Session a0b58526: the Monitor loop named lanes in its command text, so it fired "lane-rigs: gone" four times after the lane closed (rows 18062-18072); a `sleep 45; ...` status chain was blocked (17973); and at row 6044 the /tmp/claude-1000 quota ran out and lost a command's output. Pairs with the lane resume script item.

## Done when
- A `lane-status` script prints low memory, scratch volume under a threshold, and each lane in the lane file whose agent_status is not working; a Monitor until-loop can call it with no sleep chain.
- Tests cover a closed lane absent from the output and a quota line present when df reports under the threshold.

---

# herdr-phase-change carries the report-to session into the cleared prompt

Source: ~/agent-evals/queue/herdr-phase-change-carries-the-report-to-session.md

---
type: "QueueItem"
title: "herdr-phase-change carries the report-to session into the cleared prompt"
description: "A worker cleared for its next phase still knows which session to report to, with no hand-added line."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T14:32:54-06:00"}
kind: "live-edit"
status: "running"
rank: 1009
blocked_by: []
source: "scripts/.local/bin/herdr-phase-change"
components: ["script/herdr-phase-change"]
not_dup: "the prior fix orders /clear before the prompt; this adds the report-to session to the prompt, which /clear erases"
---

## Context
After /clear, a forked worker loses the brief line naming the session it reports to. The orchestrator had to tack the report-to line onto the /code command by hand.

## Done when
A test runs herdr-phase-change with a slash-command prompt and checks the sent prompt names the sending session as the report-to target; it fails before the change.

---

# herdr-phase-change resolves a ListAgents session name or worktree path

Source: ~/agent-evals/queue/herdr-phase-change-resolves-a-listagents-session.md

---
type: "QueueItem"
title: "herdr-phase-change resolves a ListAgents session name or worktree path"
description: "The orchestrator moves a worker to its next phase by the name it already has, skipping a 3k-token herdr agent list dump."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T14:32:54-06:00"}
kind: "live-edit"
status: "running"
rank: 1009
blocked_by: []
source: "scripts/.local/bin/herdr-phase-change"
components: ["script/herdr-phase-change"]
not_dup: "the prior fix orders /clear before the prompt; this resolves the target by session name or worktree path"
---

## Context
herdr-phase-change returned agent_not_found for the session name ListAgents shows; the orchestrator dumped the full herdr agent list (about 3k tokens) to find the pane id.

## Done when
A test passes a ListAgents-style session name and a worktree path; both resolve to the pane id. It fails before the change.

---

# Nothing runs the prune of merged lane worktrees: dotfiles holds 231

Source: ~/agent-evals/queue/nothing-runs-the-prune-of-merged-lane-worktrees.md

---
type: "QueueItem"
title: "Nothing runs the prune of merged lane worktrees: dotfiles holds 231"
description: "Merged, clean lane worktrees are removed when a lane merges, so worktree listings stay short and disk is freed."
generated: {"by": "claude-fable-5-2/main", "at": "2026-11-22T14:36:31-06:00"}
kind: "chore"
status: "queued"
rank: 1010
blocked_by: []
source: "scripts/tools/herdr-worktree-prune"
components: ["script/herdr-worktree-prune"]
not_dup: "The done item built the prune tool; this wires it to a step that runs, since the count rose from 213 to 231 after it shipped"
---

## Context
2026-11-22: `git worktree list` in dotfiles printed 231 worktrees. The prune tool for merged, clean lane worktrees shipped on 2026-11-15, and no step calls it. Every worktree listing a session reads carries all of them.

## Done when
- One existing step (the lane merge line, or session start) runs the prune of merged, clean lane worktrees; no new hook process.
- After one run, the worktree count is the count of unmerged or dirty lanes.

---

# hunk-review-pane names its own herdr pane review so nvim-jump finds it

Source: ~/agent-evals/queue/hunk-review-pane-names-its-own-herdr-pane-review.md

---
type: "QueueItem"
title: "hunk-review-pane names its own herdr pane review so nvim-jump finds it"
description: "A review pane started by hand opens nvim on a jump without the user renaming the pane."
generated: {"by": "claude-opus-5-5/main", "at": "2026-11-22T14:17:45-06:00"}
kind: "chore"
status: "queued"
rank: 1007
blocked_by: []
source: "scripts/.local/bin/hunk-review-pane"
components: ["script/hunk-review-pane", "script/nvim-jump"]
---

## Context

nvim-jump finds the review pane by its herdr label `review`. Only herdr-dev sets that label. A pane where the user started hunk-review-pane by hand (alias `hw`) has no label, so the first live jump failed with "no review pane for its repo could open one" until the pane was renamed by hand. The tests stubbed git and hunk, and every stub pane already carried the label, so they never covered an unlabeled pane.

## Done when

hunk-review-pane renames its own pane (`$HERDR_PANE_ID`) to `review` at start. A test starts it with a stub herdr in an unlabeled pane and checks the rename call; it fails without the change.

---

# pull_keep_index put-back still fails when the pull and the staged files both change built change pages

Source: ~/agent-evals/queue/pull-keep-index-put-back-still-fails-when-the-pull.md

---
type: "QueueItem"
title: "pull_keep_index put-back still fails when the pull and the staged files both change built change pages"
description: "After a pull that changes the built change-log pages, the staged files go back with the pages rebuilt, in one run and with no hand repair."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-22T12:04:06-06:00"}
kind: "method"
status: "queued"
rank: 1002
blocked_by: []
source: "scripts/tools/pull_keep_index.py"
components: ["script/pull-keep-index"]
not_dup: "2026-11-22-pull-keep-index-rebuilds-staged-built-pages-on-the: that fix is on master (e112a1dc) and the failure happened after it, on the first run and on the --put-back it printed"
---

## Context
2026-11-22, dotfiles master, after the fix in e112a1dc was live. Local state: 30 staged files, three of them built pages (docs/changes/changelog.md, in-progress.md, index.md), plus three unstaged edits. The pull fast-forwarded 2e9ac1f9 to f8c3c4a4, which changed the same three pages. The re-apply failed with 'patch failed: docs/changes/changelog.md:7 ... conflicts in index. Try without --index', and the tree was left with none of the local changes. The printed recovery, --put-back <save commit> on the clean tree, failed with the same three errors. --help also fails: 'git branch --show-current failed in --help'.

Hand repair that worked: apply the save commit's staged diff with the three built pages excluded (git apply --index --3way), apply its unstaged diff, run build_changes.py, stage the rebuilt pages.

## Done when
- A test builds this state (staged built pages, a pull that changes the same pages) and the run ends with every local change back, staged files staged, and the pages rebuilt.
- --put-back on that save commit does the same.
- --help prints usage.

---

# pull_keep_index in a shared checkout takes a running coder's uncommitted edits out of the tree mid-run

Source: ~/agent-evals/queue/pull-keep-index-in-a-shared-checkout-takes-a.md

---
type: "QueueItem"
title: "pull_keep_index in a shared checkout takes a running coder's uncommitted edits out of the tree mid-run"
description: "A pull by one session removed another session's uncommitted coder edits from the shared tree three times in four minutes, and one put-back failed."
generated: {"by": "claude-fable-5-2/main", "at": "2026-11-22T14:50:31-06:00"}
kind: "method"
status: "running"
rank: 1013
blocked_by: []
source: "scripts/tools/pull_keep_index.py"
components: ["script/pull-keep-index"]
not_dup: "the done item fixed the claim step telling a session to pull; the queued put-back item is about built change pages. This one is a second session's files leaving the tree while its coder and tests run"
---

## Context

2026-11-22, agent-evals main checkout, two sessions on bench-base. Session A had a coder editing
bin/build_changes.py and bin/test_build_changes.py, uncommitted. Session B committed a queue item and ran
pull_keep_index.py. Each pull saved the whole dirty tree, rebased, and put it back. For the length of each rebase the
coder's files were gone from the tree, and its test run read the old code. One put-back failed ("would be overwritten
by merge: bin/build_changes.py") because the coder wrote the file during the pull; the edits then lived only in a
dangling commit until the next pull. The coder recovered three times from dangling commits and committed early to stop
it. No work was lost in the end; a session that did not know where to look would have lost it.

## Done when

1. A pull through pull_keep_index.py in a checkout where another session has uncommitted edits either leaves those
   files in the tree for the whole pull, or refuses and names the files and the way out.
2. A put-back that fails never leaves the edits only in an unreferenced commit: it keeps a named ref and prints it.
3. A test pins both, with a second writer changing a file during the pull.
