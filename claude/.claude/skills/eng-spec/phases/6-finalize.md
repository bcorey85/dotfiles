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
    - **Testability lint**, two questions per Success Criterion. Could a reader
      of ONLY the plan decide it pass/fail (named command, output, or test)? And
      where it names a mutation a test must catch, is that mutant actually
      distinguishable through the public surface — or would the suite pass
      either way, making the criterion unfalsifiable? Failures are
      UNDERSPECIFIED — resolve with the user like a `DESIGN GAP`, never left to
      the coder's reading.
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
