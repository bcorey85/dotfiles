---
type: "Change"
change_type: "fixed"
title: "Review-fix launch test reads its own launch folder"
description: "The review-fix test for an ordinary finding plus a ruled impact reads the prompt of the fix launch's own folder, so the file system's listing order no longer decides whether it passes."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-15T09:29:47-06:00"}
seq: 2
kind: "fix"
components: ["script/review-fix", "script/tests"]
evidence: ["review-fix-test-reads-the-first-launch-folder-a"]
watches: []
test: "tests/scripts/test_review_fix_script.py::test_a_launch_with_an_ordinary_finding_and_a_ruled_impact_sends_only_the_ordinary_one"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `tests/scripts/test_review_fix_script.py`: the named test read `next(glob("*/prompt.txt"))` under `loop-script`, the first prompt in listing order. Two launch folders exist at that point (the review launch and the fix launch), so it read the review launch's prompt whenever the file system listed that folder first. It now reads `findings_files[0].parent / "prompt.txt"`, the prompt in the folder of the fix launch's single `findings.json`.
- No script under `claude/.claude/scripts/` changed. No script picks a launch folder by listing order.

Other first-of-glob lines, each judged on whether its glob can match two entries at that point:

- `test_review_fix_script.py` 2259: cannot. One launch in a fresh repo, one `review-script-*` folder.
- `test_review_fix_script.py` 2295: cannot. One launch in a fresh second repo.
- `test_review_fix_script.py` 2353 (`launched_run`): cannot. Every caller makes one launch before it in a fresh repo.
- `test_review_launch.py` 239, 261, 276: cannot. Each test makes one launch in its own fresh repo (the sibling lines already use `loop_dirs(...)[-1]` for the same folder).
- `test_verify_branch_script.py` 239 and 1384: cannot. The state file is named by repo and branch, and each test preps one branch of one repo.
- `test_verify_branch_script.py` 1976: sorted before `[0]`, so the order is fixed.
- `test_review_fixes.py` 21: cannot. Each hook script file name exists in one scripts subfolder.
- Other `glob(...)[0]`, `next(...glob(`, `list(...glob(...))[0]` and `rglob` forms in `tests/scripts`: all are sorted before use or only iterate.

## Evidence

Queue item `review-fix-test-reads-the-first-launch-folder-a`: `script-tests` failed 3 of 12 master runs on this test with `Regex didn't match: '(?m)^user-ruled: 1$' not found in 'mode: review-first\ncaller: review\nlane: none\n\nReview the working tree against HEAD.\n'`.

## Result

With the glob forced to sorted order the test failed with that same message. The folders were `review-script-20261115T092520-a00305` (review launch) and `review-script-20261115T092522-734767` (fix launch). With the reverse order it passed, which showed the order decides. After the fix the test passes in forward order, in reverse order and in 20 natural runs.

## Watch

None. A test-only change.

## Back-out

Revert the commit.
