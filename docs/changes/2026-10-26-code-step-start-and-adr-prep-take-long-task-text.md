---
type: "Change"
title: "code-step start and adr prep take long task text on Python before 3.14"
description: "code_step.py and adr_flow.py test argument words with os.path instead of pathlib, so a task text longer than a file name no longer crashes start with OSError File name too long on Python 3.13 and older."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T07:59:41-05:00"}
seq: 46
kind: "fix"
components: ["script/code-step", "script/adr-flow"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_long_task_text_reaches_the_coder_whole"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code_step.py` tests each argument word for a plan file or folder with `os.path.isfile` and `os.path.isdir` instead of `pathlib.Path(word).is_file()` and `is_dir()`. Before Python 3.14, pathlib raises `OSError: [Errno 36] File name too long` on a word longer than a file name may be, and any multi-paragraph task text passed as `start <text>` is such a word. `start` then crashed, the skill cut the task to one line, and the coder built from that line. `os.path` returns False on that error in every version. The same swap is made at every other site that tests an argument word: the `<plan> Phase <id>` check, the plan-inside-task refusal, the plan resolution and the plan load. `adr_flow.py prep` had the same crash on a long argument (`Path(argument).exists()`) and gets the same swap.

## Evidence

judgment: one work session hit the crash on a multi-paragraph `/code` brief; the coder skipped half the scope. Reproduced here under Python 3.12 and 3.13; Python 3.14 does not raise, which is why the suite never saw it. Tests run the script under the newest installed Python older than 3.14 and skip when none is present: `test_long_task_text_reaches_the_coder_whole` (positional, `+fast` and `--task` forms) fails twice on the base commit with the OSError and passes after; `test_adr_flow.py::AdrFlowTest::test_prep_refuses_long_text_instead_of_crashing` fails on the base commit with the traceback and passes after.

## Result

Full suite (2219 tests) and ruff pass.

## Watch

—

## Back-out

Revert the `os.path` swaps in `code_step.py` and `adr_flow.py`, the two tests, the `interpreter` arguments of the test helpers and `PRE_314_PYTHON` in `tests/scripts/toolkit_paths.py`.
