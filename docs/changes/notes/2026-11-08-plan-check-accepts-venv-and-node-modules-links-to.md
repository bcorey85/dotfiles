---
type: "Change"
change_type: "fixed"
title: "Plan check accepts repo links to programs outside the repo"
description: "The plan check reads whether a repo path is inside the repo from the path's own text, so any repo link to a program outside the repo, such as `.venv/bin/python` or `node_modules/.bin/<tool>`, counts as a command."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-08T23:40:23-06:00"}
seq: 14
kind: "fix"
components: ["script/plan-verification", "script/script-utils"]
evidence: ["plan-verification-rejects-venv-and-node-modules"]
watches: []
test: "tests/scripts/test_script_utils.py::test_a_venv_or_node_modules_link_to_a_target_outside_the_root_is_one"
asked: ""
proof: []
unmeasured: ""
---

## Change

`script_utils.is_executable_file_inside` checks the path's own text and checks it against the repo root, given or resolved. It no longer resolves symlinks before the check, so a link in the repo may point anywhere; the comment in `plan_verification.py` says so. An absolute path outside the repo still fails. Any path with a `..` segment now fails, including one that stays inside the repo (`bin/../bin/tool`), which the check used to accept.

## Evidence

plan-verification-rejects-venv-and-node-modules

## Result

A plan whose Automated Verification runs `.venv/bin/python -m pytest` or `node_modules/.bin/vitest` passes the plan check. Both are links to an interpreter or package outside the repo. Any repo link is judged by its own text, not only `.venv` and `node_modules`.

## Watch

—

## Back-out

Revert the commit (the `script_utils.is_executable_file_inside` change and its tests in `test_script_utils.py` and `test_plan_verification.py`).
