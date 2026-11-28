# Review finding parser keeps the list under a colon-ended finding

Two queue items. The test-run hook item is already met on master by 6f543dd68 (the foreground full-suite deny names
run_in_background alone where no systemd scope can run; test
`tests/scripts/test_memory_cap_scope.py::test_the_hook_names_run_in_background_alone_on_a_host_with_no_scope`). The
tilde half of the parser item is met on master by 7c0230fb3 (`file:~441-452` keeps its path; line 0 marks it
approximate). This plan fixes the colon half only.

## Scope

- In: `claude/.claude/scripts/review/review_loop_findings.py` (`item_start_lines`, `parse_tagged_bullets`) and
  `tests/scripts/test_review_loop_findings.py` (or the existing test file for that module).
- Out: `finding_record.py` (its location read is already right), herdr scripts, `land_lane.py`, `skills/code`, the
  comment gate.

## Phase Status

- [x] Phase 1: a finding whose text ends in a colon keeps the bullets under it (risk: low)

## Phase 1: a finding whose text ends in a colon keeps the bullets under it

Bug: a reviewer item that ends in a colon and leads into a list of cases loses the cases.

- Section format (`## Fix` and the rest): bullets at the item's own indent after a colon-ended item become separate
  findings with no location, and the lead keeps none of them.
- Tagged-bullet format (`- fix: ...`, the test reviewer): untagged bullets under a colon-ended tagged bullet, nested or
  at its indent, are dropped.

1. `item_start_lines`: a located item line whose text ends in `:` opens a notes list, like the plain lead-in line does today.
   The bullets under it continue the item until a bullet opens with a file:line, a bullet states an ask in an Ask
   section, or a plain line at the item indent closes the list.
2. `parse_tagged_bullets`: an untagged list line continues the tagged bullet before it when it is indented deeper than
   that bullet, or when that bullet's text ends in `:` and the untagged bullets follow it with no plain line between.
   A plain line at the top indent ends the continuation.
3. Everything else in both formats parses as before.

#### Automated Verification

- New tests: section format and tagged format, each with a colon-ended located lead plus two case bullets (same
  indent and nested), parse to one finding holding the lead and both cases, located at the lead's file and line, and
  the next located item stays its own finding. They fail before the change.
- A tilde fixture (`file:~441-452`) parses with its path set and line 0, and is not split.
- `python3 tests/parallel_tests.py` on the changed test file passes; `bash tests/run.sh` passes.

## Plan Deviations

- Phase 1 step 1 adds: when a colon item's notes start nested, the next marker at the item indent closes the list.
  Session ruling, owner plan, no ticket, criteria intent stays met, 2026-11-27.
- Not built: a colon on a wrapped continuation line of a finding. No real reviewer reply shows that shape, and the
  toolkit script rules send a reviewer-only case to no new code. Session ruling, 2026-11-27.
