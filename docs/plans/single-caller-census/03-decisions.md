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
