# Phase 6: Architect finalization and acceptance criteria

15. **Continue each architect via `SendMessage`** — its exploration context is
    intact. Send `03-decisions.md` **by path only** plus the instruction to produce the full plan per its Output
    Format.

    Attempt `SendMessage` first — never assume unreachable. Only on failure, re-dispatch fresh with brief verbatim + `02-research.md` + `03-decisions.md`.

    **Fullstack ordering**: finalize `backend-architect` first — its plan must
    define the **API contract** (endpoints, methods, request/response shapes,
    status codes). Then finalize `frontend-architect` _with_ that contract, so it
    designs against it, not around it.

16. **Synthesize and save `docs/plans/<slug>/spec.md`.** Read
    `~/.claude/skills/eng-spec/templates/spec-template.md` and use its format.

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
    - **Write `## Decisions` as one line per resolved block in `03-decisions.md`**:
      its number, the Choice, and the Trade-off only where it changes code. The
      full block stays in the ledger. If none exist, state why. Its
      `## Direction & Constraints` feeds `## Constraints`. Keep the ledger and
      research beside the spec.
    - **State each fact once.** A fact that a coder needs goes in one section,
      and other sections point to it. An edge case that a phase handles lives in
      that phase, not in a second list. A fact that only the user needs at the
      gate stays in its sibling file, named by path.
    - **Write `## Constraints` and `## External Contracts` yourself — both are mandatory.** Rules live in those sections' comments in the spec template; write with the template open, not from memory.
    - **Fullstack: weave, don't concatenate.** "Backend phases, then frontend
      phases" is the horizontal anti-pattern `plan-format.md` forbids — layer
      phases give `/code`'s gates no end-to-end signal. Interleave
      vertical slices, each one verifiable increment of user-observable behavior.
      Single-layer phases only when the work genuinely is.

    Write before step 16b, without a save question. After each write run
    `python3 ~/.claude/scripts/code/code_step.py plan check docs/plans/<slug>/spec.md`;
    exit 1: fix each line, rerun. All later checks use this saved spec. Persist every revision to the same file before
    continuing; never leave a repair only in conversation.

16b. **Dry-run the verification criteria** — two failure modes of the plan's
`#### Automated Verification:` commands survive reading. Resolve each with the user before Phase 7.

    - **Falsifiability run**: run
      `python3 ~/.claude/scripts/tools/criteria_dry_run.py docs/plans/<slug>/spec.md`
      once. It runs every Automated Verification command of every phase against
      the pre-implementation tree and prints `CHECK <n> RED|GREEN|BROKEN|UNPARSED`
      plus `FLAG` lines. Clean RED is good; GREEN, BROKEN or UNPARSED lets the coder
      pass with no check running. A filtered test run that matches no test reads RED
      (the test does not exist yet). A `FLAG` is a defect in the criterion: a
      `pgrep -f` that matches the shell running it, or a count that differs from
      the plan's own code. Pass `--skip <n>` for each command that writes; a
      command that writes never runs.
    - **Criteria that read a file or a diff**: open the file and confirm it holds
      what the criterion looks for, and that the container or path is the one the
      phase changes. An `rg` over prose uses `-U` and `\s+`, or a wrapped phrase
      passes unseen.

16c. **Falsify the plan's factual claims against the tree.** Step 16b checks the
verification commands; this checks the assertions the plan reasons FROM. Run
these before Phase 7 and resolve every miss with the user like a `DESIGN GAP`.

    - **Counts and inventories** — every number the plan states about the tree
      (files, tests, rows, entries, views, measures, indexes) gets its producing command, run now; state returned vs claimed side by side.
    - **Names, spellings, and paths** — every identifier, token, flag, config
      key, and path the plan quotes gets one `rg` against the tree, or one
      `--help` for a flag.
    - **Tool and dependency behavior** — every claim about what a command, flag,
      or library version does gets its `--help` or a one-line run. So does the validator or parser each new value meets.
    - **Internal agreement** — any quantity the plan states in more than one
      place must agree everywhere, and a frozen literal must match every later assertion.
    - **Batch the probes** as in 16b, in at most TWO Bash calls: counts + names +
      tool-behavior, then deny-sweep + superseded-deliverables. An ambiguous result re-runs solo.
    - **Consumers of every changed member** — for each member, helper or rule
      whose SQL, name or wording the plan changes, `rg` its name across the whole
      repo (model, views, tools, tests, oracles, docs). Every hit is named in a
      phase or ruled out in one line. Count view-level description overrides:
      they restate or hide cube text.
    - **Predicates on nullable flags** — `rg` the plan's SQL for `= false`,
      `= true` and a bare `NOT` before a helper call. Each one on a warehouse
      boolean is written `IS [NOT] TRUE` or wrapped in `COALESCE`, since a CDC
      flag can be NULL where the source says false.
    - **Work the hooks will deny** — `rg` phase bodies and change lists (not just `**File**:` lines) for hook-protected directories.
    - **Superseded deliverables** — check whether each phase's deliverable already landed on base while the spec was written. Re-building shipped work is a plan defect, not a merge conflict.

    STANDARD path: counts + names only; the rest run only on surfaces the architect flagged.

    Future claims (what a later phase produces) are 16b's and the testability lint's problem, not this step's.

17. **If the ticket has behavioral criteria**, dispatch **`spec-criteria`**
with `00-ticket.md`, `03-decisions.md`, the saved `spec.md`, and the task directory.
It writes `docs/plans/<slug>/acceptance-criteria.md` and returns the damage-path
questions it refused to default.

    Do not write the list yourself, and do not ask the architect to. Then rerun
    `plan check` on the spec (and after every edit to the list): it fails an `AC<n>` that is not
    that criterion's id; write `ticket AC<n>` for the ticket's number.

    **Open the walk with a read-back.** In 15 lines or fewer, say what the
    system will do after this ticket, in the ticket owner's words: what goes in,
    what comes out, the rules that decide it, and what happens to data that
    already exists. Leave out files, phases and code terms. A correction
    resolves like a `DESIGN GAP`.

    **Then walk the draft with the user and take strikes and corrections.** They
    hold authority over every line: put damage-path questions to them in ONE turn — policy is the ticket-owner's call, never defaulted; "out of scope" is an answer (log under `## Direction & Constraints`); silence is not. **No Phase 7 before they respond.**

    **Coverage sweep, after the user signs off the list.** For each behavioral criterion, name the phase whose `#### Automated Verification:` will produce a test for it. Prose text the LLM reads counts as behavior. A criterion that only a `rg` check, a manual step or nothing covers gets one of two fixes: add a test-verified line to the owning phase, or move the criterion to `## Manual only` with its reason. Report it as `coverage: <n> mapped, <m> fixed of <total>`.

Plan saved. Go to Phase 6.5 (fresh-eyes review + planning-lane log row) — carry `gaps` and `falsified` forward.
