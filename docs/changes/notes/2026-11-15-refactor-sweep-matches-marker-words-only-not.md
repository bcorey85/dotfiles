---
type: "Change"
change_type: "fixed"
title: "refactor sweep matches marker words only, not identifiers that hold them"
description: "The /refactor branch-prep sweep no longer lists identifiers such as tree_fingerprint( as debug prints, or TODOS_DIR as a TODO."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-15T12:34:26-06:00"}
seq: 5
kind: "fix"
components: ["skill/refactor"]
evidence: ["refactor-sweep-flags-every-identifier-ending-in"]
watches: []
test: "tests/scripts/test_refactor_flow.py::RefactorFlowTest::test_branch_prep_sweep_flags_a_marker_word_and_never_an_identifier_that_holds_one"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `SWEEP_MARKERS` in `skills/refactor/scripts/refactor_flow.py` puts a word boundary on TODO, FIXME, XXX, HACK (an optional plural `s` is flagged too, as in `# TODOs`), `console.log`/`console.debug`, `debugger` and `binding.pry`, and matches `print(` only when no word character or dot comes before it. A bare `print(` or `pprint(` and the dotted `pprint.pprint(` are still flagged.

## Evidence

Queue item `refactor-sweep-flags-every-identifier-ending-in`: a branch audit got 8 sweep matches, all false (7 were `*_fingerprint(` calls).

## Result

The named test fails on the old pattern (`tree_fingerprint(`, `TODOS_DIR`, `HACKATHON` and the other identifier cases are listed) and passes with the change.

## Watch

None. No intake number reads this.

## Back-out

Revert the commit.
