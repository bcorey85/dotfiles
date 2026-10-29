---
type: "Change"
change_type: "fixed"
title: "Metrics writers fold pairs that zsh left in one argument"
description: "kv_fold refused a value such as `lane=code scope=phase iter=1`, which is what `C=\"lane=code scope=phase\"; writer $C` sends under zsh, since zsh does not split an unquoted variable. Each word after the first is now folded as its own pair when every one of them is name=value and the key is not free text. Any other spaced value is still refused."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-24T21:34:47-05:00"}
seq: 20
kind: "fix"
components: ["script/log-escape", "script/log-scan", "script/log-spec-run", "script/log-review-finding", "script/log-review-metrics", "script/log-review-check"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_log_escape.py::LogEscapeTest::test_pairs_in_one_unsplit_argument_are_folded_one_by_one"
asked: ""
proof: []
unmeasured: ""
---

## Change

`scripts/lib/_kv.sh`:

- New `kv_unfold`. It runs over every argument before `kv_fold` judges it. An argument `key=a b=2 c=3` becomes `key=a`, `b=2` and `c=3` when every word after the first matches `name=` and `key` is not a free-text key.
- It keeps the argument whole when the value starts with whitespace, holds a tab or line break, or has any word after the first that is not `name=value`. `kv_fold` then refuses it as before.
- The free-key test moved into `kv_is_free`, shared by both functions.

Tests: two new cases in `tests/scripts/test_log_escape.py`. The first fails before the change. The second checks that a bare word after a pair is still refused.

## Evidence

- Census of this machine's toolkit script calls, 2026-10-19 to 2026-10-24: 38 refusals with "contains a space", spread over every day. 33 were followed by a successful log call within 10 minutes. One test-audit run never logged its run row and its finding rows after the refusal.
- Replaying the 32 distinct refused values through the new parser splits 26 of them. The other 6 have bare words or placeholder text and stay refused.

## Result

A writer call built from a shared pairs variable logs on the first try in zsh. A value that swallowed free text is still refused.

## Watch

None. The intake does not count writer refusals by cause.

## Back-out

Restore `scripts/lib/_kv.sh` from git and drop the two test cases.
