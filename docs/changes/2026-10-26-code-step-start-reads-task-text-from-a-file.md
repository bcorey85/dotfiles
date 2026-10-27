---
type: "Change"
title: "code_step start reads task text from a file"
description: "`code_step.py start --task-file <path>` reads the task text verbatim from any path, the code skill passes it through, and a positional non-plan file outside the repo is refused with the --task-file command."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:50:59-05:00"}
seq: 76
kind: "fix"
components: ["script/code-step", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_start_input.py::StartInputTest::test_task_file_text_reaches_the_coder_unchanged"
asked: ""
proof: []
unmeasured: "Fork rewordings and quoting stops are not logged; no intake number reads them."
---

## Change

`start --task-file <path>` reads the task text from a file inside or outside the repo; a missing, empty or unreadable file,
a flag with no path, or text after the flag exits 2. The code skill passes the flag through, and its description tells
the orchestrator to pass a long or quote-heavy task that way, from the scratchpad if it likes. A positional file outside
the repo that is no plan gets a refusal whose rerun command uses `--task-file`.

## Evidence

Three sightings of a fork rewording task text to get it past zsh quoting or a Bash hook, one of which left the coder
without the spec. One sighting of a scratchpad brief refused as a plan outside the repo.

## Result

Task text reaches the coder unchanged with no shell quoting in the path; a scratchpad brief starts the coder.

## Watch

None.

## Back-out

Revert the commit.
