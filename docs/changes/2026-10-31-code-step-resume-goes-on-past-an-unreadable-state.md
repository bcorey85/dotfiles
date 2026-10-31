---
type: "Change"
change_type: "fixed"
title: "code-step resume goes on past an unreadable state file in the cwd checkout"
description: "A /code run in a sibling worktree finishes its steps when the session's own checkout holds another run's state file this code-step cannot read."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-31T15:46:01-05:00"}
seq: 405
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_checkout.py::CheckoutTest::test_an_unreadable_state_in_the_cwd_checkout_does_not_block_the_open_run_in_another_checkout"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `resume_run_repos` in `code_step_core.py`: when the cwd checkout's state file raises `StateFileError` and that
  file's raw JSON names another session or a finished run, it reads the session's other checkouts and returns those
  that hold its open run, so the verb goes on there. The session's own unfinished run, an unreadable or non-object
  file, or no other open run re-raises, and the unreadable-state stop still fires. A readable cwd state keeps the cwd-first rule.

## Evidence

judgment: twice in one session, a /code run given a sibling worktree stopped at every resume. The session's main
checkout held a state file that carried a key this code-step does not know. Resume read that file first and stopped,
so the coder's work went unreviewed by the run.

## Result

The named test fails before (the verb stops on the unknown key) and passes after.
`test_an_unreadable_state_in_the_cwd_checkout_with_no_other_open_run_still_stops` passes before and after.

## Watch

None.

## Back-out

In `code_step_core.py`: restore the original `resume_run_repos` body (no `try`/`except StateFileError`), delete
`state_text_names_another_session_or_done_run`, drop the `except_repo` parameter of `session_open_run_repos`, and drop
the `state_file_text` and `StateFileError` imports. In `code_step_store.py`: delete `state_file_text` and `state_text_at`, and put
the verb-or-disk text read back inline in `read_state_file`. In `test_code_step_checkout.py`: delete the new tests
(unreadable state in the cwd checkout, in a checkout the session started a run in, in a subdirectory, with no other
open run, of the session's own open run, naming no session, naming another session or a done stage, and non-object or
non-JSON state), the `leave_unreadable_state` and `resume_run_repos_from` helpers, and the `pathlib` and
`unittest.mock` imports.
