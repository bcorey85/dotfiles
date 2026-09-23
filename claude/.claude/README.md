# Claude Code toolkit

Agents, skills, hooks, and rules for Claude Code. Stowed to `~/.claude/`.
Why the agents have this shape: [docs/agent-evals.md](../../docs/agent-evals.md).

## Ticket lifecycle, end to end

```
/triage → /eng-spec → /clear → /code (per phase: read queue → stage → /commit)
        → /refactor → /verify → /test-audit → /branch-recap → /adr → /commit → PR
```

Small work skips the spec: `/triage` routes XS–M tickets directly to `/code`.
A bug with an unknown cause goes to `/debug` first, then back to `/triage`.

### 1. `/triage <TICKET>` — size and route

Read-only. It pulls the ticket (`/pull-ticket`), bounds the surface in 8 tool
calls or fewer, and prints an LoE bucket (XS–XL or `?`) plus the route:
`/eng-spec` with a depth (STANDARD or DEEP), `/code`, or `/debug`. It never
designs. If no ticket exists for L/XL work, it offers `/create-ticket`.

### 2. `/eng-spec <TICKET>` — plan, never implement

Create the branch first (`TICKET-NUM-desc`). `/commit` refuses to run on
master. All artifacts persist in `docs/plans/<slug>/`.

| Phase       | What happens                                                                                               | Agents                                                                           | Artifact                            |
| ----------- | ---------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- | ----------------------------------- |
| 1 Ticket    | Resolve the input                                                                                          | —                                                                                | `00-ticket.md`                      |
| 2 Research  | Goal-blind research. The research agent never sees the ticket                                              | `goal-blind-researcher` → `spec-questions` → `spec-leak-check` → `spec-research` | `01-questions.md`, `02-research.md` |
| 3 Scope     | Pick the depth: GO-LEAN, STANDARD, or DEEP                                                                 | —                                                                                | —                                   |
| 4 Explore   | Architects explore. No design yet                                                                          | `backend-architect`, `frontend-architect`                                        | —                                   |
| 5 Decisions | You resolve each design decision, one at a time                                                            | —                                                                                | `03-decisions.md`                   |
| 6 Finalize  | Architects finalize (backend first, then frontend with its contract). Planning checks. Acceptance criteria | architects, `spec-criteria`                                                      | `spec.md`, `acceptance-criteria.md` |
| 6.5 Review  | Fresh-eyes plan review. STANDARD 1 round, DEEP 2 rounds                                                    | `plan-reviewer`                                                                  | repairs to `spec.md`                |
| 7 Handoff   | Stop. Print the `/code` command                                                                            | —                                                                                | —                                   |

GO-LEAN skips phases 4 and 5. Research always runs before design.

Commit the plan directory here if you want it on the branch before code starts.

### 3. `/clear`, then `/code docs/plans/<slug>/spec.md` — one phase at a time

Each phase runs this sequence:

1. `coder` implements the phase. Coders write no tests.
2. `test-writer` writes tests from the plan criteria. It never sees the coder diff.
3. `review-loop` runs review → fix until it converges: `code-reviewer`, plus
   `security-reviewer`, `perf-reviewer`, and `smell-reviewer` when the diff
   touches their surface.
4. Phase gates: drift gate, then `test-intent-reviewer` (when tests changed).
5. `/stage` stages the mechanical SAFE tier and orders the rest as a read queue.
6. The phase line in `## Phase Status` is checked off.

Then the phase boundary:

- **Stop for sign-off**: phase 1, `(risk: high)`, any gate exception, and the
  last phase. Read the queue, run the human-only checks, `git add` what you
  read, then `/commit`. Confirm to start the next phase.
- **Auto-advance**: `(risk: low)` phases with all gates green. Commit at the
  next stop.

`/commit` drafts the message from the staged diff, scans for secrets, commits,
and pushes. It never stages. `review-commit-gate` blocks `git commit` while a
coder dispatch is unreviewed.

### 4. Closing phases — after the last `/code` phase

| Order | Skill           | Job                                                                    | Agents                                                                 |
| ----- | --------------- | ---------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| 1     | `/refactor`     | Branch-wide structure pass                                             | `smell-reviewer` (`complexity-reviewer` if one module grew ≥100 lines) |
| 2     | `/verify`       | Plan ↔ diff completeness, smoke-test checklist                         | `plan-verifier`                                                        |
| 3     | `/test-audit`   | Cross-phase test gate: cull, lost coverage, weak assertions            | `test-intent-reviewer`, fixes via `/fix` and `test-writer`             |
| 4     | `/branch-recap` | One pre-PR sheet: `/stage` residue, deferred findings, recap. No gates | —                                                                      |

Read the residue queue, stage it, then `/commit`.

### 5. `/adr`, then the PR

`/adr` collapses the task directory into a decision record. Stage it, `/commit`,
and open the PR yourself. The ADR ships in the same PR as the code.

### After merge

If a defect got past the gates, log it with `/escape`. `/audit review`
aggregates the escapes.
