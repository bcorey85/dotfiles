# Phase 6: Architect finalization and acceptance criteria

15. **Continue each architect via `SendMessage`** — its exploration context is
    intact. Send `03-decisions.md` **by path only** plus the instruction to produce the full plan per its Output
    Format.

    Attempt `SendMessage` first — never assume unreachable. Only on failure, re-dispatch fresh with brief verbatim + `02-research.md` + `03-decisions.md`.

    **Fullstack ordering**: finalize `backend-architect` first — its plan must
    define the **API contract** (endpoints, methods, request/response shapes,
    status codes). Then finalize `frontend-architect` _with_ that contract, so it
    designs against it, not around it.

16. **Synthesize the finalized plan(s).**

    - **`DESIGN GAPS` returned by an architect**: resolve each with the user in
      prose (step 14's rule holds), append it to `03-decisions.md` as a decision
      block, **then send the resolution back to that architect** and take its
      revised plan.
    - **Testability lint**, one question per Success Criterion: could a reader of
      ONLY the plan decide it pass/fail (named command, output, or test)? A
      failure is UNDERSPECIFIED — resolve with the user like a `DESIGN GAP`, never
      left to the coder's reading. (Falsifiability is checked in step 16b.)
    - **Carry the counter-priming into `## Approaches Considered and Not Taken`**
      — the ruled-out approaches the architect actually named, each with its
      failure mode, and its own count where it named fewer than three. Never top
      the list up.
    - **Write `## Constraints` and `## External Contracts` yourself — both are mandatory.** Rules live in those sections' comments in the spec template; write with the template open, not from memory.

    - **Fullstack: weave, don't concatenate.** "Backend phases, then frontend
      phases" is the horizontal anti-pattern `plan-format.md` forbids — layer
      phases give `/code`'s gates no end-to-end signal. Interleave
      vertical slices, each one verifiable increment of user-observable behavior.
      Single-layer phases only when the work genuinely is.

16b. **Dry-run the verification criteria** — two failure modes of the plan's
`#### Automated Verification:` commands survive reading. Resolve each with the user before Phase 7.

    - **Static lint**: `bash ~/.claude/scripts/spec-criteria-lint.sh <plan-path>`
      flags a test-file `**File**:` target and a verification-command file that no
      phase creates and is absent.
    - **Falsifiability run**: for each **read-only** command (build, test, lint,
      `git grep` — never one that writes), run it as written against the pre-implementation tree. Clean RED is good; already-GREEN or BROKEN-on-bad-flag lets the coder pass with no check running.

16c. **Falsify the plan's factual claims against the tree.** Step 16b checks the
verification commands; this checks the assertions the plan reasons FROM. Run
these before Phase 7 and resolve every miss with the user like a `DESIGN GAP`.

    - **Counts and inventories** — every number the plan states about the tree
      (files, tests, rows, entries, views, measures, indexes) gets its producing command, run now; state returned vs claimed side by side.
    - **Names, spellings, and paths** — every identifier, token, flag, config
      key, and path the plan quotes gets one `rg` against the tree, or one
      `--help` for a flag.
    - **Tool and dependency behavior** — every claim about what a command, flag,
      or library version does gets its `--help` or a one-line run.
    - **Internal agreement** — any quantity the plan states in more than one
      place must agree everywhere, and a frozen literal must match every later assertion.
    - **Work the hooks will deny** — `rg` phase bodies and change lists (not just `**File**:` lines) for test-file paths. A test edit assigned to the coder is denied outright and routes to the test-writer. Same for hook-protected directories.
    - **Superseded deliverables** — check whether each phase's deliverable already landed on base while the spec was written. Re-building shipped work is a plan defect, not a merge conflict.

    Future claims (what a later phase produces) are 16b's and the testability lint's problem, not this step's.

17. **If the ticket has behavioral criteria**, dispatch **`spec-criteria`**
with `00-ticket.md`, `03-decisions.md`, the finalized
plan, and the task directory. It writes
`docs/plans/<slug>/acceptance-criteria.md` and returns the damage-path
questions it refused to default.

    Do not write the list yourself, and do not ask the architect to.

    **Then walk the draft with the user and take strikes and corrections.** They
    hold authority over every line: put damage-path questions to them in ONE turn — policy is the ticket-owner's call, never defaulted; "out of scope" is an answer (log under `## Direction & Constraints`); silence is not. **No Phase 7 before they respond.**

Plan final. Go to Phase 6.5 (fresh-eyes review + planning-lane log row) — carry `gaps` and `falsified` forward.
