# Phase 7: Handoff

18. **Stop after planning.** Keep `<task dir>/spec.md` (`<task dir>` = the task directory phase 1 step 3 opened) and its supporting
    artifacts on disk. Never ask whether to save or implement, never dispatch a
    coder, and never invoke `/code` in this conversation.

    First run `python3 ~/.claude/scripts/code/plan_check.py check --final <task dir>/spec.md`.
    Exit 1 is an unresolved planning gate: fix each row it prints, and run it again.

    Any unresolved planning gate → report what remains and stop without an
    implementation handoff. Otherwise, give the saved spec path and say:

    > Plan saved. Clear this conversation with `/clear`, then run
    > `/code <task dir>/spec.md`.

    Substitute the actual absolute path. Do not clear the conversation yourself.
