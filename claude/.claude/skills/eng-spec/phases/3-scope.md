# Phase 3: Scope

7. **Determine scope** (frontend / backend / fullstack) from the ticket, the
   research, and the codebase. If genuinely ambiguous, ask. Then state it: "This
   is [scope]. I'll spin up [architects]. Sound right?"

8. **Pick the depth.** Default is STANDARD. State it in one line; confirm with
   the user when not obvious.

   - GO-LEAN: skip Phases 4–6 only if ALL of these hold:
     - Pure configuration with zero implementation choices (install a package, add
       an env var, flip a flag)
     - No new files, no changed service/module signatures
     - No data-model, API-contract, or state-management decisions
     - The whole change is under 5 lines of diff; err downward when the diff is near it
   - STANDARD: real decisions but bounded — single-layer OR ≤3 phases, no
     migration/endpoint/dependency the ticket did not imply, nothing destructive
     (reclaim/expire/evict/revoke/invalidate). Architects run; step 16b full,
     step 16c counts + names only; max 1 review round.
   - DEEP: anything else. Full Phases 4–6b.

   Upgrade mid-run: queue >5 decisions or any scope-gate trip → DEEP, say so.

   **A well-written ticket is NOT a reason to go lean.** An "Approach" section is
   context FOR an architect, not a replacement.

   Go-lean handling: confirm with the user, write the plan from existing patterns,
   and **still dispatch a coder in Phase 7** if they implement. In the saved spec,
   `## Decisions` reads `None — pure configuration; the constraints that forced it
are under Constraints.` and `## Approaches Considered and Not Taken` reads
   `N/A — go-lean path (no architect ran)`.

   **Wanting to write a real decision block means the lean call was wrong.**
   Back out and dispatch the architect.
