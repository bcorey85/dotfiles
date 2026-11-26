# Decisions

- Ruling by session feature/single-caller-census (criteria owner `session`) at 2026-11-25: the superseded-helper check
  keeps its guard that the old helper's call passes at least one argument. With no argument, nothing ties the newer
  helper's call to the old one, so every newer function the caller calls would match. This reads AC3's "same output"
  through its mechanical proxy (the newer call takes every argument of the old call); it overrides the phase-1 ask
  ruling that dropped the guard.
- Ruling by session feature/single-caller-census at 2026-11-25: the forwarder rule lists a def whose body is any one
  `return`, as AC1 says, not only a return of a call.
- Ruling by session feature/single-caller-census at 2026-11-25: `changed_line_sets` moves from `clone_pairs.py` to
  `lib/changed_lines.py` so the census and `/refactor` share it; `shape_clones.py` imports it from there.
- Ruling by session feature/single-caller-census at 2026-11-25: Phase 1 closes at the review cap with the full suite
  green (7049 tests) and lint clean. Left as they are: the untracked symlink skip (no session hit it), the textconv
  blame test gap (the diff side is tested) and the test-helper placement nit.
- Ruling by session feature/single-caller-census at 2026-11-25: the review loop's call keeps `census_base` at its
  default (work tree against HEAD). Passing `self.review_base` is a one-line edit at `review_loop_script.py:444`, a
  file outside this lane; it goes to the orchestrator as a follow-up. AC4 holds in the loop's default mode; a run
  with `--base` reads the census against HEAD.
- Ruling by session feature/single-caller-census at 2026-11-25 (review asks): ask 1, keep `census_base` and leave
  `review_loop_script.py:444` to its owning lane as a follow-up (the earlier ruling stands). Ask 2 accepted: "newer"
  compares H's def-line blame time with F's. The SKILL.md step sentence is reverted: no SKILL.md prose in this lane,
  and branch-prep prints the census in the prompt the skill already hands on. `report_lines` is renamed to clear the
  duplicate-check clash with `stale_prose.py`; `census_lines` folds into it.
- Ruling by session feature/single-caller-census at 2026-11-25 (merge review stop): the review of merge 2dc886cc1
  covers its three conflict resolutions only, and its code reviewer found them clean. The loop's 15 edits to
  merged-in files are reverted and saved as a patch for their owners. Its asks on `review_launch.py:256` and
  `announced_step.py:53` go to those files' owners. Its ask to read the census at the review base is rejected per
  the census_base ruling above.
- Ruling by session feature/single-caller-census at 2026-11-26 (lane review stop): the census reads its added lines
  through the merged-in owner `lib/change_added_ranges.py`, with `relative` and `no_renames` options, and checks spans
  with `diff_ranges.ranges_touch` and `ranges_cover`; both lib files join the Scope. The three asks stay rejected:
  census at HEAD (earlier ruling), the line re-cite, and `test_session_registry` coverage (merged-in file).
- Ruling by session feature/single-caller-census at 2026-11-26 (lane review asks, round 3): the plan deviation's
  "plan line 30" re-cite is accepted. `diff_ranges.ranges_touch`/`ranges_cover` and `changed_lines.range_touched`/
  `range_added` both stay: `changed_lines` serves the span diffs `refactor_flow` hands `clone_pairs` and
  `shape_clones`, which `change_added_ranges` cannot produce; folding them is a follow-up. The
  `detect_renames`/`no_renames` guard is dropped with its test: no caller passes both.
- Ruling by session feature/single-caller-census at 2026-11-26 (lane review asks, round 4): the plan deviation now
  cites plan.md:31-33 (applied by the session). The quoted `+++` name decode in `diff_ranges.py` is rejected and
  reverted with its test and the `test_uncommitted_change.py` edit: only a reviewer raised it, it changed a merged-in
  script's output, and it duplicated `source_text._header_path`.
