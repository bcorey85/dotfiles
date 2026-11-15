---
type: "Change"
change_type: "fixed"
title: "A /review fix run follows a no-code ruling on an ask"
description: "A finding whose ask was ruled no code change reaches the fix coder as a named constraint, and a code edit against it is flagged in the packet and checked by the next reviewer."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-15T10:08:11-06:00"}
seq: 2
kind: "fix"
components: ["script/review-loop", "script/review-fix-asks", "script/handback", "script/ruled-change-text", "script/source-paths"]
evidence: ["review-fix-coder-ignores-a-no-code-ask-ruling"]
watches: []
test: "tests/scripts/test_review_loop_ruled.py::NoCodeRulingTest::test_a_code_edit_against_a_no_code_ruling_is_flagged_and_a_doc_edit_is_not"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New `lib/ruled_change_text.py` owns the ruler clauses (user, session, unnamed), the shared `; make this change in its place: ` marker, `ruled_note` (reads the note after the last marker, so the latest ruling wins) and `is_no_code_ruling` (`\bno code change`, any case). `changed_text` takes the ruler's clause from every caller. `review/review_fix_asks.py` builds finding text through it, so a no-code note is read whoever ruled.
- `review/review_loop_prompts.py` `coder_prompt` adds a `## No code change` section naming the issue numbers: edit no source or test file for them, make only the doc or note edit, else `SKIPPED <n>: <reason>`.
- `review/review_loop_ruled.py` flags each code file (not `lib/source_paths.py` `is_doc_path`) the coder changed for a no-code finding, also when the coder call fails. The packet carries `no_code_ruling_broken` (`{ruling, file}`: the ruling's location and note, not the coder brief's private issue number); `review/handback.py` renders it as `Code changed against a no-code ruling: <file> (ruling: <ruling>)`. The next `reviewer_prompt` lists the rulings and asks for a `[plan-drift]` finding.
- `claude/.claude/scripts/CLAUDE.md` names `lib/ruled_change_text.py` as the owner of the ruling text. The user approved the line directly on 2026-11-15.

## Evidence

Queue item `review-fix-coder-ignores-a-no-code-ask-ruling`: a session ruled an ask "no code change; add one Watch line to the change note" and the fix coder added code anyway. Note shapes taken from real `review-fix/ask-findings.md` files.

## Result

The named test, the other `test_review_loop_ruled.py` and `test_ruled_change_text.py` tests and the two new `test_review_loop_script.py` tests fail on the old scripts (import error: no owner module) and pass with the change. `test_handback.py` adds the render and packet-error tests.

## Watch

None. No intake number reads this.

## Back-out

Revert the commit. The packet key is new and read only by `handback.py`.

