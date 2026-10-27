# Phase 7: Handoff

18. **Stop after planning.** Keep `docs/plans/<slug>/spec.md` and its supporting
    artifacts on disk. Never ask whether to save or implement, never dispatch a
    coder, and never invoke `/code` in this conversation.

    First run `python3 ~/.claude/scripts/code/code_step.py plan check --final docs/plans/<slug>/spec.md`.
    Exit 1 is an unresolved planning gate: fix each row it prints, and run it again.

    Any unresolved planning gate → report what remains and stop without an
    implementation handoff. Otherwise, give the saved spec path and say:

    > Plan saved. Clear this conversation with `/clear`, then run
    > `/code docs/plans/<slug>/spec.md`.

    Substitute the actual path. Do not clear the conversation yourself.
