---
type: "Change"
change_type: "fixed"
title: "phase_start moves a stale stop.md aside so the next stop is a new file"
description: "phase_start.py renames an existing stop.md of the run folder to stop.prev.md, so the /code fork's Write of its next stop is no longer refused; code_relay hands a bounced stop.prev.md on once."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-13T10:00:00-06:00"}
seq: 3
kind: "fix"
components: ["script/phase-start", "script/code-relay"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_phase_start.py::PhaseStartTest::test_a_stale_stop_file_is_renamed_to_stop_prev_replacing_an_older_one"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code/phase_start.py` renames `<run folder>/stop.md` to `stop.prev.md` (replacing an older one) before it records the
phase start. `lib/stop_file_names.py` names it `PREVIOUS_STOP_FILE`, outside `STOP_FILES`, so the relay hands it on
only once, as a bounced stop.md not yet relayed, and otherwise exits 1 on a run that wrote no new stop. A failed rename
prints the error on stderr naming phase_start and the script goes on. `review-stop.md` is left alone.

`code/code_relay.py` reads `stop.prev.md` only when it is the newest stop file. Then the relay hands it on once if it is
a bounced stop.md not yet relayed (`relay_bounced_stop`), with the unreviewed note while the tree is still edited after
the clean review; otherwise it exits 1 instead of relaying an older stop. Test:
`tests/scripts/test_code_relay.py::ReviewedTreeRelayTest::test_a_bounced_stop_moved_aside_by_phase_start_relays_once_with_the_unreviewed_note`.

## Evidence

judgment: the fork's Write refused a stop.md left over from an earlier stop that it had not read, the stop lived only in
the reply, and a later resume read the old stop.

## Result

The new test fails on the old tree (stop.md stays) and passes.

## Watch

None: a fixed rule.

## Back-out

Revert the commit.
