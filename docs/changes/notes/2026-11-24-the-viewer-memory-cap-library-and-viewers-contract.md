---
type: "Change"
change_type: "added"
title: "the viewer memory-cap library and --viewers contract land (lane-tools-1123 Phase 0)"
description: "A sourced bash library now owns the hunk viewer's memory cap, its value grammar, the availability check and the systemd scope prefix, so the viewer start and lane-status can share one definition."
generated: {"by": "claude-opus-5-5/main", "at": "2026-11-24T09:39:52-06:00"}
seq: 1
kind: "fix"
components: ["script/viewer-memory"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_viewer_memory.py::ViewerMemoryTest::test_an_oom_kill_result_reads_as_killed"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`scripts/.local/lib/viewer-memory.bash` (new, sourced) holds the cap `HUNK_REVIEW_MEMORY_MAX` (default 1G, digits then
K, M or G, base 1024) and the restart window `HUNK_REVIEW_RESTART_WINDOW_SECONDS` (default 60, digits). It provides
`viewer_memory_checked` (a bad value returns 1 and names the variable on stderr), `viewer_memory_max_bytes`,
`memory_cap_available` (Linux, `systemd-run`, `systemctl`, and a user bus), `set_viewer_cap_prefix <unit>` (the
`systemd-run --user --scope` array with `MemoryMax` and `MemorySwapMax=0`, or empty when no cap is available) and
`viewer_scope_was_oom_killed <unit>` (reads the scope's `Result`, always resets the failed unit). The header documents
the `--viewers` JSON shape that `hunk-review-pane` and `lane-status` will share. `memory_cap_scope.py` gains a comment
naming the bash twin of `cap_available`. `tests/scripts/test_viewer_memory.py` covers the grammar, the prefix and the
OOM read.

## Evidence

Judgment: the contract is frozen first so the viewer start and the lane-status read cannot drift apart.

## Result

No behavior changes yet: nothing sources the library. The library tests pass.

## Watch

None: no viewer runs under the cap until the next phase.

## Back-out

Delete `scripts/.local/lib/viewer-memory.bash`, `tests/scripts/test_viewer_memory.py` and the two comment lines in
`claude/.claude/scripts/lib/memory_cap_scope.py`.
