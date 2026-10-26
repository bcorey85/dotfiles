---
type: "Change"
title: "Code-step tests jump through a fake nvim-jump, never the user's Neovim"
description: "code_step.py present_asks reads the nvim-jump command from CODE_STEP_NVIM_JUMP, like review_fix.py's REVIEW_FIX_NVIM_JUMP, and the code-step tests set it to a fake, so a test run no longer opens its temp files in the user's Neovim."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T19:14:13-05:00"}
seq: 7
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_review_asks_jump_through_the_set_nvim_jump_and_never_the_one_on_path"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code/code_step.py` `present_asks` runs the command named by `CODE_STEP_NVIM_JUMP`, default `nvim-jump`. No run
sets it, so a session jumps as before.

The tests set it: `test_code_step.py` to a fake that logs its arguments, `test_code_step_termination.py` and
`test_fixes.py` to `true`. `test_code_step_asks.py` already stubs `run_command`.

## Evidence

`present_asks` ran the real `nvim-jump` whenever `shutil.which` found it, and no code-step test stubbed it. Each
review-ask test opened its temp `backend/src/orders.ts` in the user's live Neovim. That Neovim's lcd autocmd started
a vtsls per temp root: 98 of them, about 18 GB, during the suite runs of 2026-10-25. The machine ran out of memory
and a suite run was killed.

With the override hard-coded back to `nvim-jump`, the new test fails: the `nvim-jump` on its PATH runs and the fake
never does.

## Result

Filled in at hand-over.

## Watch

None. Test-suite side effects have no intake number.

## Back-out

Revert the commit.
