# Phase 7: User choice

18. **HARD STOP — no spec write, no coder dispatch, until the user answers.**

    Ask both questions in ONE **AskUserQuestion** call ("Save to disk?" and
    "Implement now?") — the blocking modal is what makes this stop unskippable,
    and it is the **ONLY legal `AskUserQuestion` in the skill**. Presenting the
    plan in conversation is fine; writing or dispatching before the answers is not.

    **Save to disk?**
    - Yes → read `~/.claude/skills/eng-spec/templates/spec-template.md`, write to
      `docs/plans/<slug>/spec.md`. Its `## Decisions` is **copied from
      `03-decisions.md`**, block for block — never re-derived from the
      conversation, never summarized. `## Direction & Constraints` from the ledger
      feeds `## Constraints`. The research and decision artifacts stay beside the
      spec as evidence.
    - No → the spec stays in the conversation, and the task directory is removed.

    **Implement now?**
    - Yes, **more than one phase** → the spec must be saved (save it even if they
      said no above — explain why), then invoke `/code` with the spec path.
      `/code`'s phase-boundary machinery keys off the plan's risk tags; a raw
      coder dispatch bypasses every gate the plan just defined.
    - Yes, single-phase → dispatch one `coder` with the whole spec, whatever
      layers it spans. **Always dispatch a coder. Never implement inline** — the
      dispatch is what triggers the review chain. If the spec calls for tests,
      dispatch `test-writer` **after** the coder returns, from the plan's
      criteria — never the same agent for both. An implementation's author
      writes tests that pin what it does, not what was asked for.
    - Later → stop here.

19. **Present summary**: key decisions, file written (if saved), what was
    implemented (if coded). Remind the user to check Figma if frontend work is
    involved.

    **If any code changed this session**, say: "Auto-dispatching `/review` to
    check the implementation before committing," then invoke `/review`. The
    review is triggered by code changing, not by how it changed — never skip it
    because no coder was dispatched.
