# Research Questions

1. How does `lib/merge_free_base.py` compute its base, and which callers use it? Trace how each caller obtains a base ref for a diff.
2. How does the review loop choose the base it diffs the branch against?
3. How does `review/review_loop_scope_guard.py` decide which files are in scope, which files it puts back, and how does it learn which files a fix pass changed? Where is its state kept?
4. How does the scope guard represent and compare the file paths it encounters?
5. How do the review loop's stop packet and blocker lines get built (`review/review_blocker_text.py`, `handback.py`), and what do they record about files a fix pass changed?
6. How do the sibling loop parts (`review_loop_ruled_out.py`, `review_loop_untracked.py`, `review_loop_signoffs.py`, `lib/protected_lines.py`) restore or reject fix-pass changes, and how do they relate to the scope guard?
7. How does the review loop file and handle an ask (`approval-asks.json`, `phase_asks.py`, `lib/ruled_change_text.py`) when a fix changes text?
8. How is plan text parsed in `lib/plan_format.py`?
9. What types, state fields, and JSON keys describe the review run's fix-pass results and changed-file lists (`review/review_fix_state.py`, `lib/review_fix_names.py`)?
10. What test patterns exist for the scope guard and review loop (`tests/scripts/` files, fixtures, `toolkit_paths.py`)? Where are the tests that cover putting back out-of-scope files, and how do they set up repos and fix passes?

## Exploration Map

- `claude/.claude/scripts/review/review_loop_scope_guard.py` — current scope guard behavior
- `claude/.claude/scripts/lib/merge_free_base.py` — base computation owner
- `claude/.claude/scripts/review/` — review loop mixins, stop packet, hand-back, fix state
- `claude/.claude/scripts/lib/` — shared modules for plan format, asks, protected lines, review names
- `claude/.claude/scripts/code/` — plan check helpers
- `tests/scripts/` — tests and path helpers for the review loop and scope guard
