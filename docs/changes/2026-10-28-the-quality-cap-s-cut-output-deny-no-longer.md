---
type: "Change"
title: "The quality cap's cut-output deny no longer rebuilds the command"
description: "The deny after a check whose output went through tail, head or grep rebuilt the command from its split steps and could cut it inside a $( ) substitution; it now names the redirect form with a <check> placeholder."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T18:57:40-05:00"}
seq: 200
kind: "fix"
components: ["script/quality-check-cap"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_quality_check_cap.py::QualityCheckCapTest::test_the_cut_deny_never_suggests_a_command_cut_inside_a_substitution"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `quality_check_cap.py`: the cut-output deny says to run the check once more with no tail, head or grep after it and
  its output sent to a file, `<check> > /tmp/check.log 2>&1`, with any file list written out rather than built by a
  `$( )` substitution. It no longer pastes a command rebuilt from the split steps, so the step splitter's cut inside a
  substitution never reaches the suggestion. The rebuilt-command field and the cd-prefix list that fed it are gone.

## Evidence

- A deny for `ruff check $(git diff --name-only | grep ...) | grep ...` suggested
  `ruff check $(git diff --name-only > /tmp/check.log 2>&1`, which is not valid shell. Coders, reviewers and sessions
  hit it on test reruns.

## Result

- The new test fails before (the deny holds the cut command) and passes after. The test that the filled-in form is
  allowed covers a cd prefix, a wrapper and an env prefix.

## Watch

—

## Back-out

Revert the commit.
