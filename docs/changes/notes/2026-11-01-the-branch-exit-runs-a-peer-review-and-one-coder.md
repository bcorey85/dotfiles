---
type: "Change"
change_type: "changed"
title: "The branch exit runs a peer review and one coder dispatch"
description: "The /verify-branch exit review is now a report-only peer review plus one coder dispatch that fixes every finding, nits included. On the bench it caught and fixed as much as the full review loop for 82% fewer Opus tokens (23.18M → 4.09M) and about a third of the wall time."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T08:16:01-06:00"}
seq: 451
kind: "structured"
components: ["skill/verify-branch", "shared/closing-phases", "script/verify-prep", "script/verify-log"]
evidence: ["bench"]
watches: ["branch-exit-peer-review-escapes", "branch-exit-peer-review-opus-tokens"]
test: ""
asked: ""
proof: ["2026-11-01-peer-review-plus-one-coder-dispatch-nits-included", "2026-11-01-a-peer-review-pass-with-one-coder-dispatch-matches"]
unmeasured: ""
overlap: "Ten open watches read review escapes per code-reviewer run; this one ships anyway because the bench already showed the single pass catches and fixes as much as the loop, and the escape watch only guards against a drop at work. Its reading after 2026-11-01 cannot be told apart from code-plain-steps-review-escapes (2026-11-02)."
impact: {"metric": "tokens", "before": 23180000, "after": 4090000, "unit": "tokens", "finding": "2026-11-01-peer-review-plus-one-coder-dispatch-nits-included"}
---

## Change

- `skills/verify-branch/SKILL.md` Step 1: the `code-reviewer` reports only and labels each finding
  blocker/ask/fix/nit with a failure scenario and a proposed change. The main session reads the diff for anything the
  reviewer missed, then dispatches `coder` once with every finding, nits included. An ask takes its proposed change
  unless that change cuts or changes a ticket AC; that ask goes to the user. The review is logged after the fixes.
- The `/review` routing on a blocker and the deferral of non-blocking findings are gone.
- `verify-prep` prints the new prompt and steps. `verify-log review` accepts only `fixed` or `skipped_fp`, plus `ask`
  on an ask the user must rule on; `deferred` and `none` are refused for every finding, blocker or not.
- `_shared/closing-phases.md` item 3 states the same pass.
- `/review base=<ref>` stays as a manual full-branch loop.

## Evidence

Bench, 8 paired runs on three fixtures, blind-graded: the exit review (`/review base=`, full loop) against the peer
review plus one coder with nits included, both on the same seeded branch.

## Result

- Seeded defects caught: exit 12, peer 13. Fixes landed: exit 12, peer 13. Unnamed fixes: 0 in both.
- On the strict reading (a catch only as a clause inside another finding does not count): peer 11 caught and fixed.
- Opus tokens: 23.18M → 4.09M. Cost: $46.20 → $12.52. Mean wall time: 20.4 → 6.2 min.
- New defects the fixes introduced: exit 2, peer 1 (minor).

## Watch

- `branch-exit-peer-review-escapes` (review-gate escapes per code-reviewer run, flat): a rise means the single pass
  misses what the loop caught at work.
- `branch-exit-peer-review-opus-tokens` (Opus main-session cache-read tokens per verify-branch turn, down).

## Back-out

Revert this commit: Step 1, verify-prep's printed steps and verify-log's outcome check return to the blocker-routed
loop with deferral.
