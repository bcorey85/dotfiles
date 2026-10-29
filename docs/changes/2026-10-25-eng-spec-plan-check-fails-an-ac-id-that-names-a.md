---
type: "Change"
change_type: "fixed"
title: "eng-spec plan check fails an AC id that names a different criterion"
description: "plan check now fails a bare AC reference in spec.md that is not that criterion's id. Before, the spec was written before the criteria file, so its bare AC numbers carried the ticket's numbering while the criteria file numbered its own."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T23:34:50-05:00"}
seq: 32
kind: "fix"
components: ["script/code-step", "skill/eng-spec"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_spec_ac_check.py::PlanCheckAcTest::test_mismatched_reference_fails_the_check_and_names_the_line"
asked: ""
proof: []
unmeasured: "A mismatch is caught at write time, so it leaves no later row; the intake has no count of spec-to-criteria id errors."
---

## Change

- `lib/plan_format.py`: `ac_reference_failures` and `spec_ac_failures` read the criteria file once and check every bare AC reference in spec.md. A bare reference passes when the criteria file has that id and the spec line (or the next) shares two content words with its text. A reference written `ticket AC<n>` is never checked. With no criteria file, every bare reference fails.
- `code/code_step.py plan check`: for a file named spec.md, prints those rows and exits 1.
- `skills/eng-spec/phases/6-finalize.md`: step 16 runs `plan check` after each spec write; step 17 reruns it after the criteria file is written or edited.

## Evidence

judgment: a peer's two eng-spec runs each had spec references that pointed at a different criterion than the same number in the criteria file (ten in the first); both plan reviewers flagged it. A wrong mapping makes the verify step pair criteria with the wrong tests.

## Result

Installed in the fix/eng-spec-ac-and-scope branch; takes effect when merged.

## Watch

None.

## Back-out

Remove the `spec_ac_failures` call from `command_plan` and the two `plan check` sentences in the finalize phase file.
