---
type: "Change"
change_type: "added"
title: "Review loop labels each docs finding stale or new from the diff"
description: "`review_loop_script.py` logs each docs-class finding of every loop reviewer with `docs_kind=stale` when the cited line stood before the change under review, and `docs_kind=new` when the change added the line. The script computes the label from the diff; no model passes it. A finding the script cannot place carries no label."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-15T13:16:03-06:00"}
seq: 5
kind: "fix"
components: ["script/review-loop-script", "script/review-loop-docs-kind", "script/log-review-finding", "script/diff-ranges", "script/ledger-write"]
evidence: ["tests", "telemetry"]
watches: []
test: "tests/scripts/test_docs_kind.py::LoopRowsTest::test_round_one_labels_each_docs_row_against_the_change_under_review"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `lib/diff_ranges.py`: `added_ranges(diff_text)` returns, per file, the line runs the diff added. `changed_ranges` and `hunk_runs` take `added_only`; their default output is unchanged.
- New `review/review_loop_docs_kind.py`: `change_added_ranges(repo, base)` reads one `git diff` of the change under review, with untracked files counted whole. `docs_kind(repo, added, finding)` returns `new` for a docs finding whose cited line is an added line, `stale` for any other line of a file in the repo, and no label for a finding of another class, a finding with no file and line, a path outside the repo, or a round with no diff.
- `review/review_loop_script.py`: round one labels against the change under review, a later round against the previous round's fix diff. `finding_log_command` appends `docs_kind=` to the logger call when a label is set. Every loop reviewer's docs row carries it; the intake counts the code reviewer's only. A resumed loop's first round carries none. A finding filed again in a later round gets its label again from that round's diff, class and line.
- `skills/review/log-review-finding`: accepts `docs_kind=stale|new` on a docs row and refuses any other value or class. When the ledger refuses the field, the row lands without it and `{finding_id, docs_kind}` goes to `~/.claude/review-finding-labels.jsonl` through `ledger-write --local review_finding_label`.
- `telemetry/ledger-write`: new type `review_finding_label`, file `review-finding-labels.jsonl`.

## Evidence

Two coder edits aim at prose a change makes false: the hand-back gate's stale-prose list (2026-10-25) and the coder rule to update stale prose after a review fix (2026-11-02). Both watches read every docs finding per code-reviewer run and both read NO CHANGE. The docs class mixes two things: prose that stood before the diff, which the edits target, and prose the diff itself added, which they do not. No row said which.

The label was run over the saved review-loop states of this machine's own branches. Round two: 55 docs findings, 26 new, 27 stale, 2 with no label. Round one, on the 17 loops whose reviewed tree could be rebuilt: 18 new, 8 stale. Of 18 labels read by hand, 17 were right and 1 was unclear.

## Result

`tests/scripts/test_docs_kind.py` holds 26 tests: added ranges, the change under review (edited, untracked, staged, renamed, with a base commit), the label for relative and absolute paths, loop rows in round one, round two, a resumed round with no diff and a docs finding filed again under another class, and the logger with a ledger that refuses the field and with no ledger.

The intake side is in agent-evals: `bin/docs_kind.py` fills the label on the merged rows by `finding_id` and prints docs findings per code-reviewer run by label, round and week. The two coder watches read the `stale` label only.

## Watch

None of its own. It changes what the watches `stale-prose-handback-docs-findings` and `coder-updates-stale-docs` count: from the first labeled day they read stale docs findings per code-reviewer run. Neither has a labeled before window, so each prints its level and no verdict.

## Back-out

Revert the commit. Rows already logged keep the label; the intake reads rows without one as unlabeled.
