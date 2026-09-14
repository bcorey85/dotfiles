# Phase 3: Scope

7. **Determine scope** (frontend / backend / fullstack) from the ticket, the
   research, and the codebase. If genuinely ambiguous, ask. State the scope and
   which architects will run.

8. **Pick the depth.** Default is STANDARD. State it in one line; confirm with
   the user when not obvious.

   - GO-LEAN: skip Phases 4–5 and step 15 only if ALL of these hold:
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

   A well-written ticket does not qualify for GO-LEAN. Apply every condition
   above, regardless of whether the ticket supplies an approach.

   Go-lean handling: confirm the depth with the user, draft the plan from existing
   patterns, then enter Phase 6 at step 16 for persistence, checks, and review.
   Use STANDARD's check depth and review-round cap. `## Decisions` reads
   `None — pure configuration; see Constraints.` and
   `## Approaches Considered and Not Taken` reads `N/A — go-lean path (no architect ran)`.

   Any real design decision invalidates GO-LEAN: dispatch the architect.
