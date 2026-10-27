---
type: "Change"
title: "A cancelled spec leaves no research file behind"
description: "eng-spec's research phase deletes the questions file before it stops the researcher, and spec-research writes nothing when its questions file is gone."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:46:03-05:00"}
seq: 100
kind: "fix"
components: ["skill/eng-spec", "agent/spec-research"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_a_cancelled_spec_deletes_its_questions_file_and_research_writes_nothing_without_it"
asked: ""
proof: []
unmeasured: ""
---

## Change

- eng-spec phase 2: when the user cancels during research, delete the questions file (`01-questions.md`)
  first, then stop goal-blind-researcher. The task directory stays.
- spec-research: before it verifies and writes, it Globs its questions file; when the file is gone it writes nothing
  and returns `cancelled: questions file removed`.

## Evidence

- A cancelled spec's research child kept running after its parent was stopped, wrote `02-research.md` into the
  removed task directory, and handed back cancelled work read from a tree a coder was rewriting. Stopping a parent
  agent does not reach its children, so the child has to see the cancel itself.
- The test pins both rules; it fails on the base tree.

## Result

- See the branch's suite run. The child still spends its run until the check; it no longer writes or hands back
  research.

## Watch

—

## Back-out

Revert the commit.
