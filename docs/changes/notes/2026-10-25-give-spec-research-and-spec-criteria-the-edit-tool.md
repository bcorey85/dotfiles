---
type: "Change"
change_type: "fixed"
title: "Give spec-research and spec-criteria the Edit tool"
description: "Agents that write a file they may later correct now have Edit, so a blocked sed -i no longer pushes them to an inline Python rewrite."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-25T22:54:04-05:00"}
seq: 27
kind: "fix"
components: ["agent/spec-research", "agent/spec-criteria"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_spec_agent_tools.py::SpecAgentToolsTest::test_every_spec_agent_that_writes_a_file_can_also_edit_it"
asked: ""
proof: []
unmeasured: ""
---

## Change

Added Edit to the tools line of spec-research and spec-criteria. spec-questions already had it. No prompt text changed.

## Evidence

When the shell write gate blocked a `sed -i` on its own research file, spec-research (Write but no Edit) rewrote the file with an inline Python script, the blocked form in another shape. spec-criteria also writes a file and had no Edit.

## Result

Both agents can correct their own file with Edit. No existing test covered agent frontmatter tools, so a new one, `tests/scripts/test_spec_agent_tools.py`, fails before (spec-research and spec-criteria lack Edit) and passes after.

## Watch

None. No intake number reads this.

## Back-out

Remove `, Edit` from the tools line of both agent files.
