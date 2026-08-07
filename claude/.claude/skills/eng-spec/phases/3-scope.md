# Phase 3: Scope

7. **Determine scope** (frontend / backend / fullstack) from the ticket, the
   research, and the codebase. If genuinely ambiguous, ask. Then state it: "This
   is [scope]. I'll spin up [architects]. Sound right?"

8. **Go lean?** Default is NO — run the architects. Skip Phases 4–6 only if ALL
   of these hold:

   - Pure configuration with zero implementation choices (install a package, add
     an env var, flip a flag)
   - No new files, no changed service/module signatures
   - No data-model, API-contract, or state-management decisions
   - The whole change is under 5 lines of diff

   **A well-written ticket is NOT a reason to skip the architect.** A ticket
   describes the PM's intended approach; the architect is what validates it
   against the codebase. An "Approach" section is context FOR one, not a
   replacement.

   If skipping: confirm with the user, write the plan from existing patterns, and
   **still dispatch a coder in Phase 7** if they implement. In the saved spec,
   `## Decisions` reads `None — pure configuration; the constraints that forced it
are under Constraints.` and `## Approaches Considered and Not Taken` reads
   `N/A — go-lean path (no architect ran)`.

   **Wanting to write a real decision block means the go-lean call was wrong.**
   Back out and dispatch the architect.
