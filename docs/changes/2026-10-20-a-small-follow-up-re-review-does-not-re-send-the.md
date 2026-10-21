---
type: "Change"
title: "A small follow-up re-review does not re-send the structure and test reviewers"
description: "When /code reviews again after the coder that applies accepted asks, or after a plan ruling, and that coder's own change is small, the review carries `structure-pass: skip` and the review loop sends only the code reviewer."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-20T18:46:31-05:00"}
seq: 7
components: ["agent/review-loop", "script/code-step"]
evidence: ["census", "judgment"]
watches: ["structure-pass-skip-escapes"]
---

## Change

- `agents/review-loop.md` Step 3a: the structure and test reviewers go out beside the first review only when the args hold no `structure-pass: skip` line.
- `scripts/code-step.py`: the review dispatch after an asks coder or a ruling adds `structure-pass: skip` when a review already ran in the phase and the follow-up coder added under 40 non-test lines and no new non-test source file. A ruling with no coder gets the line. A first review never gets it. The round cap reset is unchanged.

The code reviewer still reads every follow-up change, with its own structure step.

## Evidence

Before code-step, the review loop sent the structure and test reviewers only on the first review of a large diff. code-step resets the round counter after the asks coder and after a ruling, so every follow-up review counted as a first review and measured the whole phase diff again. A bench run on this machine reported that every follow-up round sent all three reviewers, at 2 to 3 minutes each.

Work logs, excluding the dotfiles and agent-evals repos, on re-reviews at round 2 or later with diffs up to 20 lines: the code reviewer had 49 runs and 12 fixed findings. The structure reviewer had 6 runs and 3 fixed findings. The test reviewer had 1 run and 0 findings. No escape names the structure or test reviewer as the gate that missed it. The sample is small.

## Result

Installed 2026-10-20. The review-loop line and the code-step header are both live.

## Watch

`structure-pass-skip-escapes`: review escapes per review run, expected flat.

## Back-out

Remove the `structure-pass: skip` clause from Step 3a and the header line from code-step's review dispatch.
