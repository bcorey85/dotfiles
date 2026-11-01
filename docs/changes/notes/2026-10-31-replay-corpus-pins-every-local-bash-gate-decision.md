---
type: "Change"
change_type: "added"
title: "Replay corpus pins every local Bash gate decision"
description: "A labelled corpus of 64 hand-written Bash calls now replays through shell-write-gate, git-discipline-gate, the inline-interpreter hint and the pipe-shell check on every suite run, and fails on any must-deny bypass or decision against its label. Before, a gate edit was checked only by its own unit tests, with no side-by-side count of denials, redundant denials, bypasses, deny-text tokens and latency against an earlier ref."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-31T21:37:42-05:00"}
seq: 406
kind: "fix"
components: ["script/shell-write-gate", "script/git-discipline-gate", "script/inline-interpreter-hint", "script/pipe-shell-check"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_gate_replay.py::GateReplayTest::test_working_tree_meets_every_corpus_label"
asked: ""
proof: []
unmeasured: "The replay runs in the suite, not at work: it leaves no intake row, and the work logs carry no local-gate tags to read."
---

## Change

- `tests/scripts/gate_replay_corpus.json`: 64 calls written by hand, 13 to 18 per gate. Each carries `expect` (allow or deny), `mustDeny` (a security-critical deny), `redundant` (a deny bash-safety-gate.sh already issues for the call), `source`, and an optional `open` note that names where a known mismatch is tracked.
- `tests/scripts/gate_replay.py`: runs each call through a fresh gate process in a throwaway fixture repo, and prints per gate the denials, redundant denials, must-deny bypasses, deny-text tokens (characters / 4) and median fresh-process latency. `--ref <git ref>` extracts the scripts folder at that ref with `git archive` and prints its row beside the working tree. Exits 1 on a working-tree bypass, a mismatch with no open note, or an open call that now matches.
- `tests/scripts/test_gate_replay.py`: runs the full corpus on every `bash tests/run.sh`, and pins the bypass, mismatch, open-note, bad-label and `--ref` paths on small corpora.

## Evidence

census: the commands are seeded from the work-log rule tags that overlap the local gates (interpreter_inline, interpreter_stdin, pipe_shell, git_push_main, git_force_push, git_reset_clean, sed_inplace_protected, tee_redirect_protected, scripted_write_protected), from the false positives in agent-evals WORK-SECURITY-HOOKS.md, and from the local-gate queue items. No command text comes from a work row.

## Result

Working tree against origin/master, both at 7c208d36 gate code: shell-write-gate 8 denials, 0 redundant, 0 bypasses, 698 deny-text tokens; git-discipline-gate 8, 0, 0, 698; inline-interpreter hint 12, 8, 0, 1719; pipe-shell check 7, 6, 0, 0. Five calls are open known mismatches: the hint misses `python3 -Ic`, denies `rg -n python -C 3`, a uv pip install with `--python ... -r`, and a heredoc body naming `python3 -c`; the pipe-shell check denies an rg alternation holding `|zsh` when the quoted pattern holds a backslash.

## Watch

None.

## Back-out

Delete the three files under `tests/scripts/`.
