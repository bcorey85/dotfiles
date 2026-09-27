---
name: drive
description: Learning mode. Build a project one change at a time in the main session, jumping nvim to each change, and advance only after the user explains it back. Use for "drive mode", "learning mode", "walk me through building X", or a vault roadmap iteration the user wants to learn by building. Not for delivery work — that is /code or /eng-spec.
allowed-tools: [Bash, Read, Edit, Write, Glob, Grep, AskUserQuestion, Skill]
---

# Drive

Learning mode. I write each change, the user reads it in their editor, and nothing advances until they can explain it. The goal is ownership, not speed.

**This skill overrides the orchestration rule "never code directly".** In `/drive` the main session writes every change, because a headless coder is what the user is learning to stop depending on. No coder dispatch and no review-loop inside a step.

## Input

- A vault roadmap iteration (for example `Legal Billing Sandbox iteration 1`): read the roadmap under `~/vault/projects/active/<project>/` and use that iteration's concepts, `Assumes:`, `Build:` and `Done when:`.
- A free-text task.
- No arguments: read the `## Where I am` block of each active roadmap and ask which one.

## Instructions

1. **Prerequisites first.** List what the work assumes: the `Assumes:` line, plus anything the steps need that it omits. For each one, ask the user: known, or teach first? Never assert "you already know this". Teach each unknown one before step 1, with something the user can run and see.

2. **Step list.** Break the work into ordered steps. One step is one file change of about 40 lines at most, and it introduces at most one new concept. Order the steps so each one runs or tests something: a thin path through data, API and report, not all tables first. Show the list as `N. path — what — concept`. The user approves or edits it. Write no code before approval.

3. **Each step, one per turn:**
   1. **Frame** in 2–3 lines: what the file is for, the one concept it introduces, and how it connects to the previous step.
   2. **Design call**, only when the step picks a shape (a name, a table layout, a boundary): ask the user to make the call in one line first, then give yours and why. "You pick" is a valid answer; then state your choice and its one tradeoff.
   3. **Predict**, for steps with logic: ask what they expect the code to do before you show it.
   4. **Write** the change with Write or Edit, then `nvim-jump <path>:<first changed line>` per `~/.claude/skills/_shared/nvim-jump.md`.
   5. **Walk it** top to bottom by line number. Name every symbol and piece of syntax that is new to them: operators, casts, placeholders, decorators, generics.
   6. **Gate.** Ask the user to explain the change back in 1–3 sentences, in their own words.
      - Correct: run the step's check (compile, test, curl or query) if it has one, show the output, and advance.
      - Gap: ask which kind — a missing prerequisite, or a bad explanation? Teach the prerequisite, or re-explain with a different framing. Gate again. Never advance past a failed gate.

4. **Commands the user can give at any time:**
   - `why`: go deeper on the current line.
   - `back`: reopen the previous step.
   - `park`: record the open question and advance.
   - `stop`: end the session (step 5).

5. **Session end.**
   - Rewrite the roadmap's `## Where I am` block — never append: last touched, done through (iteration and step), next step, machine state.
   - List parked questions and offer to add them to the roadmap.
   - Offer a `notes/` entry for each concept that clicked, following the vault's `CLAUDE.md`. Do not write it unasked.
   - Commit only when the user asks. No review is required, because no coder ran. Suggest `/review` at the end of an iteration.

## Rules

- One concept per step. If a step needs two, split it.
- Never write code for a later step early.
- A test the user has not read does not count as understood.
