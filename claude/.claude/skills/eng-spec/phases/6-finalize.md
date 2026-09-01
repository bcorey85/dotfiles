# Phase 6: Architect finalization and acceptance criteria

15. **Continue each architect via `SendMessage`** — its exploration context is
    intact. Send `03-decisions.md` **by path only** (re-typing from context is
    compaction-lossy) plus the instruction to produce the full plan per its Output
    Format. Do NOT re-litigate resolved decisions; they carry the user's authority.

    **Never assume an architect is unreachable — attempt the call.** Only after
    `SendMessage` fails, re-dispatch fresh with its brief verbatim,
    `02-research.md`, and `03-decisions.md`.

    **Fullstack ordering**: finalize `backend-architect` first — its plan must
    define the **API contract** (endpoints, methods, request/response shapes,
    status codes). Then finalize `frontend-architect` _with_ that contract, so it
    designs against it, not around it.

16. **Synthesize the finalized plan(s).**

    - **`DESIGN GAPS` returned by an architect**: resolve each with the user in
      prose (step 14's rule holds), append it to `03-decisions.md` as a decision
      block, **then send the resolution back to that architect** and take its
      revised plan. Its guess may have shaped steps and criteria well past the
      flagged line; hand-patching one spot leaves the rest built on the guess.
    - **Testability lint**, one question per Success Criterion: could a reader of
      ONLY the plan decide it pass/fail (named command, output, or test)? A
      failure is UNDERSPECIFIED — resolve with the user like a `DESIGN GAP`, never
      left to the coder's reading. (Falsifiability is checked in step 16b.)
    - **Carry the counter-priming into `## Approaches Considered and Not Taken`**
      — the ruled-out approaches the architect actually named, each with its
      failure mode, and its own count where it named fewer than three. Never top
      the list up: an invented approach reads later as one genuinely considered
      and rejected.
    - **Write `## Constraints` and `## External Contracts` yourself — nothing
      upstream produces them**, and both are mandatory. Their full rules live in
      those two sections' comments in the spec template; write them from the
      template open in front of you, not from memory.

    - **Fullstack: weave, don't concatenate.** "Backend phases, then frontend
      phases" is the horizontal anti-pattern `plan-format.md` forbids — layer
      phases give `/code`'s gates no end-to-end pass/fail signal. Interleave
      vertical slices, each one verifiable increment of user-observable behavior.
      Single-layer phases only when the work genuinely is.

16b. **Dry-run the verification criteria** — two failure modes of the plan's
`#### Automated Verification:` commands survive reading. Resolve each with the
user before Phase 7.

    - **Static lint**: `bash ~/.claude/scripts/spec-criteria-lint.sh <plan-path>`
      flags a test-file `**File**:` target and a verification-command file that no
      phase creates and is absent.
    - **Falsifiability run**: for each **read-only** command (build, test, lint,
      `git grep` — never one that writes), run it as written against the
      pre-implementation tree. Clean RED is good; already GREEN, or BROKEN on a
      bad flag with zero checks run, lets the coder pass without a check running.

16c. **Falsify the plan's factual claims against the tree.** Step 16b checks the
verification commands; this checks the assertions the plan reasons FROM. Every
one of them was captured during exploration, and the tree has moved since —
including by earlier phases of this same plan. Run these before Phase 7 and
resolve every miss with the user like a `DESIGN GAP`. A wrong premise here
cannot be caught by any later reviewer: the code will match the plan exactly.

    - **Counts and inventories** — every number the plan states about the tree
      (files, collected tests, rows, entries, views, measures, indexes) gets the
      command that produces it, run now. State the number the command returned
      next to the one the plan claims.
    - **Names, spellings, and paths** — every identifier, token, flag, config
      key, and path the plan quotes gets one `rg` against the tree, or one
      `--help` for a flag. In prose, the wrong spelling of a real thing and the
      real name of a deleted thing read identically.
    - **Tool and dependency behavior** — every claim about what a command, flag,
      or library version does gets its `--help` or a one-line run. Repeated
      flags, removed parameters, and silently-ignored options are the recurring
      shape.
    - **Internal agreement** — any quantity the plan states in more than one
      place must agree in all of them, and a phase that freezes a literal must
      match every later phase that asserts it. A coder trusting whichever copy
      it read first ships the wrong one.
    - **Work the hooks will deny** — `rg` the phase bodies and change lists, not
      just `**File**:` lines, for test-file paths. A test edit assigned to the
      implementing coder is denied outright; it routes to the test-writer from
      the criteria. The same goes for any path under a directory this repo's
      hooks protect.
    - **Superseded deliverables** — for each phase, check whether what it builds
      already landed on the base branch while the spec was being written. A
      phase that re-builds shipped work is a plan defect, not a merge conflict.

    Claims that are genuinely about the future (what a later phase will produce)
    are out of scope here — they are 16b's problem, and step 16's testability
    lint's.

17. **If the ticket has behavioral criteria**, dispatch **`spec-criteria`**
(pinned — omit `model`) with `00-ticket.md`, `03-decisions.md`, the finalized
plan, and the task directory. It writes
`docs/plans/<slug>/acceptance-criteria.md` and returns the damage-path
questions it refused to default.

    Do not write the list yourself, and do not ask the architect to — an agent
    that just justified this design writes criteria that restate it.

    **Then walk the draft with the user and take strikes and corrections.** They
    hold authority over every line; the draft only saves them from re-saying in
    prose what Phase 5 already settled. Put the returned damage-path questions to
    them in ONE turn — policy there is the ticket-owner's call, never defaulted,
    and "out of scope" is an answer (log it under `## Direction & Constraints`).
    Silence is not. **The user must respond before Phase 7.**

18. **Log the plan.** One row, once, when the plan is finalized:

    ```bash
    bash ~/.claude/scripts/log-spec-run \
      repo="$(basename "$(git rev-parse --show-toplevel)")" \
      slug=<task dir basename> ticket=<ID|none> verdict=finalized \
      phases=<count> criteria=<count> decisions=<count> \
      research_q=<count> gaps=<count> falsified=<count>
    ```

    Count them, do not estimate: `criteria` is every `Success Criteria` bullet
    across all phases plus every id in `acceptance-criteria.md`; `gaps` is the
    DESIGN GAP items raised and resolved during planning; `falsified` is how many
    factual claims the sweep two steps up actually found wrong and repaired.
    `falsified=0` is a real answer and must be logged as one.

    Log a row with `verdict=abandoned` instead if the plan is dropped after
    research — planning that produced no code is still planning that was paid for,
    and leaving it out makes the lane look cheaper than it was.

    Non-blocking: if the script fails, say so in one line and continue. Without
    this row a later count of plan defects has no denominator and cannot be read.
