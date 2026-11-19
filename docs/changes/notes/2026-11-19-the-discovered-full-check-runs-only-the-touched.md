---
type: "Change"
change_type: "fixed"
title: "the discovered full check runs only the touched parts, each on its own"
description: "The discovered full check runs only the frontend package or Python backend a changed path falls in, every part when a path is outside all of them, and a part that cannot start does not stop the others."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T06:39:45-06:00"}
seq: 3
kind: "fix"
components: ["script/check-discovery", "script/full-check", "script/full-check-gate"]
evidence: ["review-full-check-ignores-frontend-only-changes"]
watches: []
test: "tests/scripts/test_check_discovery.py::ChangedPathPartsTest::test_a_frontend_only_change_gives_only_the_package_part"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code/check_discovery.py` picks the parts by the path kind of each changed path and joins them so each part runs and
reports on its own; a 127 in one part never hides a failing code in another. `review/full_check.py` passes the
diff's changed paths.

## Evidence

A frontend-only change ran the Python backend suite, which failed on its own setup and hid the frontend result.

## Result

`test_check_discovery.py` ChangedPathPartsTest; `test_check_parts.py` JoinPartsTest and ReadPartsTest; new tests in `test_full_check.py`.

## Watch

None.

## Back-out

Revert the commit.
