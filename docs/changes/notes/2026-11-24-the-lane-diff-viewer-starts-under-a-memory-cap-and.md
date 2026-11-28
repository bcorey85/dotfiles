---
type: "Change"
change_type: "added"
title: "the lane diff viewer starts under a memory cap and restarts after an OOM kill"
description: "hunk-review-pane now runs hunk in a systemd user scope capped at 1G on both start paths, restarts it after an OOM kill, and lists viewers with --viewers."
generated: {"by": "claude-opus-5-5/main", "at": "2026-11-24T09:41:54-06:00"}
seq: 2
kind: "fix"
components: ["script/hunk-review-pane"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_hunk_review_pane.py::HunkReviewPaneCapTest::test_launcher_starts_hunk_under_the_memory_cap"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`scripts/.local/bin/hunk-review-pane` sources `viewer-memory.bash` and runs every hunk start through `run_viewer`, in
a herdr pane and from a plain terminal alike. Each start is a fresh `systemd-run --user --scope` unit with
`MemoryMax=$HUNK_REVIEW_MEMORY_MAX` (default 1G) and no swap. A bad cap exits 2 naming the variable before hunk starts.
Off Linux, with no systemd-run/systemctl, or with no user bus, hunk runs uncapped; a scope that fails to start stops the launcher. When the scope was
OOM-killed (or hunk exits 137 under a cap), the terminal is reset, one line names the cap, and hunk restarts; a kill
within `HUNK_REVIEW_RESTART_WINDOW_SECONDS` of the start waits for Enter and stops on end of input. `--viewers` prints
the cap in bytes and one row per state dir with a `hunk.pid`; an empty `hunk.pid` (the extension is mid-write) is skipped. `.claude/rules/hunk.md` gains one sentence.

## Evidence

Judgment: the launcher tests run it against stub `systemd-run`, `systemctl` and `hunk`.

## Result

The viewer cannot grow past the cap unnoticed; a kill is reported and the viewer comes back.

## Watch

None: a pane reopened on this branch shows the scope in `/proc/<pid>/cgroup`.

## Back-out

Revert the commit: the launcher goes back to `exec hunk diff`.
