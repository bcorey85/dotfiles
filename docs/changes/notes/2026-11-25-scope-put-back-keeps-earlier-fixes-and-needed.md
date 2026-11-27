---
type: "Change"
change_type: "changed"
title: "Scope put-back keeps earlier fixes and needed files"
description: "The review loop keeps a file a fix pass changed outside its scope when the pass's gate needs it, and stops naming the file and the folder of its bytes for any other."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T20:49:31-06:00"}
seq: 7
kind: "fix"
components: ["script/review-loop"]
evidence: ["tests/scripts/test_review_loop_scope_guard.py"]
watches: []
test: "tests/scripts/test_review_loop_scope_guard.py::ScopeGuardLoopTest::test_a_stray_file_the_gate_needs_stays_and_counts_as_touched"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`review/review_loop_scope_guard.py` puts back each file a fix pass changed outside its scope as before, then judges the files it put back (those whose bytes it saved and those the pass deleted) with the pass's gate. The gate is the caller's test commands, else the ones derived for the reviewed and touched files (`review/review_loop_stray_files.py`, a `LoopRun` mixin). With the files put back, a passing gate means the fix does not need them; a failing gate that passes once the saved bytes are copied back means the files together are needed, and each file is then judged alone: the gate runs with every other file in the pass's state and this one put back, and a file is kept only when the gate fails that way; the loop stops over the rest. Any other result (passes without, fails either way, no gate runs) sets `stray_blocker`, and `repair` raises `StrayFileError`, which the loop reports as a `critical-blocker` naming each file and the put-back folder that holds its bytes. A failed pass is only put back, with no gate run. `files_touched` already held every pass's changed files through the callers of `repair`, so a later put-back never undoes an earlier pass's hunks; a pass that stops on a stray file adds its files before it raises.

## Evidence

`test_review_loop_scope_guard.py` covers the three verdicts and a pass with nothing outside its scope at the guard, and, through the loop, a stray file the gate does not need, one with no gate, and one the gate needs.

## Result

One stray file costs two gate runs (put back, restored); n strays cost n + 2 runs, each the phase's scoped test commands, never the full suite. That is more than one full suite only when one scoped run costs over 1/(n + 2) of it; no run was timed, so this is a bound, not a measurement.

Before, a stray file was reverted and noted in `tool_fault` only, even when the fix needed it. Walking every put-back found none that reverts an earlier round's hunk, so the earlier-fix scope was already right; the loop tests pin it.

## Watch

—

## Back-out

Revert the commit.
