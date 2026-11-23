# Design Decisions — review-owner-1122

> Research: ./02-research.md
> Status: 16/16 resolved

## Queue

- [x] D1. Where the owner-lines-only grammar lives — from backend-architect
- [x] D2. How the decision log records the owner-line ruling — from backend-architect
- [x] D3. When and from where the ruling is read — from backend-architect
- [x] D4. Which CLAUDE.md path the exception covers — from backend-architect
- [x] D5. What counts as owner-lines-only (deletes, merges, reorders) — from backend-architect
- [x] D6. Partial edits: owner line plus another change in the same file — from backend-architect
- [x] D7. How a kept edit is reported in the packet — from backend-architect
- [x] D8. Where the pre-pass text for the diff comes from — from backend-architect
- [x] D9. Item 2 route: prose rule with meter arms, or close on evidence with a replay test — from backend-architect
- [x] D10. `criteria_owner` reads only the first Source line: fail-open on mixed authorship — from backend-architect
- [x] Q1. Does "Owners lines: none in any CLAUDE.md" retire the Owners section? — from backend-architect
- [x] Q2. Glossary: widen "standing ruling" and "approval-only file"; add "owner line" — from backend-architect
- [x] Q3. Who writes the `Standing ruling … covers: owner-lines` line in a lane's decision log — from backend-architect
- [x] Q4. Item 2 premise: is there a real failing replay? — from backend-architect
- [x] Q5. Fix D10 in this lane or queue it — from backend-architect
- [x] Q6. Merge order with `fix/toolkit-rules-nov22` — from backend-architect

## Resolved

### D1. Where the owner-lines-only grammar lives

**Choice**: A new module `claude/.claude/scripts/lib/owner_lines.py` owns the scripts CLAUDE.md path constant, the `## Owners` heading name, the owner bullet form and the `owner_lines_only(before_text, after_text)` test. A two-sided changed-line helper (before and after line numbers per opcode) goes beside `changed_stretches` in `lib/protected_lines.py`. The module's owner is stated in its docstring; no line is added to `scripts/CLAUDE.md` (standing ruling by agent-evals-c3 at 2026-11-22, see Direction).
**Reasoning**: Lane call under the brief's rulings, 2026-11-22. The scripts rules place a fact by what it knows and give each format one reader; the file format knows nothing of the review loop.
**Alternatives rejected**: Inside `review_loop_ruled.py`: the file format would be parsed where the loop mixin lives, and the dead-pass caller in `review_loop_partial_fix.py` would reach the grammar only through the mixin. A second regex in a gate later would have no owner to import.
**Trade-off accepted**: One more module and one more test file.

### D2. How the decision log records the owner-line ruling

**Choice**: Extend the standing-ruling form in `lib/standing_rulings.py`: `covers:` takes `rewords` or `owner-lines`. Add `owner_line_ruling(plan_path)` beside `reword_ruling`; `reword_ruling` keeps filtering on `rewords`, so `code/plan_check.py:48` (off-limits) needs no edit.
**Reasoning**: Lane call, 2026-11-22. One form, one reader, malformed lines already raise `PlanFormatError name:line:`. The glossary wording then lags the code (Q2, sent to the user through agent-evals-c3; non-blocking).
**Alternatives rejected**: A new line form (`Owner-line ruling by …`): a second ruling grammar, two readers for one kind of fact, and a lane that writes the wrong one gets a silent revert and an ask. Matching sign-off line text: fuzzy, so a paraphrase in a sign-off would keep an edit nobody ruled on.
**Trade-off accepted**: The `standing_rulings.py` docstring and the glossary entry say "a user's ruling"; the code now accepts a session's. Both texts need the user's yes to change (Q2).

### D3. When and from where the ruling is read

**Choice**: Pre-pass, in `snapshot_approval_blobs`, from the work-tree `03-decisions.md` of the run's plan, stored on the host beside the blob snapshot.
**Reasoning**: Lane call, 2026-11-22. Sign-off protection puts back only lost lines (`protected_lines.entries_missing`), so a coder pass can add a ruling line that survives; a post-pass read would let the coder authorize its own edit.
**Alternatives rejected**: The decision log at HEAD: lane plans are uncommitted mid-phase, so the ruling would read as absent and every owner-line edit would still be reverted. Post-pass: the self-authorization hole above.
**Trade-off accepted**: A ruling written after the snapshot and before the pass is missed; the edit is reverted and asked as today.

### D4. Which CLAUDE.md path the exception covers

**Choice**: Exact repo-relative `claude/.claude/scripts/CLAUDE.md`.
**Reasoning**: Lane call, 2026-11-22. It is the one file with an `## Owners` convention and the one the global sentence names.
**Alternatives rejected**: Any path ending `scripts/CLAUDE.md`: another repo's file of that name has no Owners section, so a bullet-shaped edit there would be kept with no convention behind it.
**Trade-off accepted**: A move of the file needs a constant change.

### D5. What counts as owner-lines-only

**Choice**: Every removed line and every added line lies inside `## Owners` (removed lines in the before-text section, added lines in the after-text section), every one matches the bullet form `- <fact>: \`<dir>/<name>.py\` …`, and the heading line is unchanged. A pure delete opcode is reverted. A replace with fewer after-lines than before-lines (lines merged or dropped) is reverted. A reorder shows as a delete and is reverted.
**Reasoning**: Lane call, 2026-11-22. The exception covers adding or updating an owner line; dropping one removes a fact's owner from the file that tells readers to import it. All 72 owner bullets ever added match the bullet form (research §1).
**Alternatives rejected**: Treat a shrinking replace as an update: a coder could fold two owners into one line and lose a pointer with no ask. Match any line in the section: a prose line or a nested bullet would pass as an owner line.
**Trade-off accepted**: A legitimate merge of two bullets goes back through the ask.

### D6. Partial edits

**Choice**: An edit with any non-owner changed line reverts the whole file, as today.
**Reasoning**: Lane call, 2026-11-22. The AC reads "whose only changed lines are owner lines … still reverts every other CLAUDE.md edit"; nobody has hit the mixed case.
**Alternatives rejected**: Keep the owner lines and put back only the rest through `restore_protected_lines`: new code for a case no session hit (scripts rules, Size), and a half-kept file whose ask text would not match its remaining diff.
**Trade-off accepted**: A coder that fixes an owner line and a prose line in one pass loses both and gets one ask.

### D7. How a kept edit is reported

**Choice**: A `drop_asks` entry with a new reason constant in `review_loop_findings.py`, text "kept under the standing ruling by <who> at <date>".
**Reasoning**: Lane call, 2026-11-22. The packet then shows the edit stood and which ruling covered it; the user is not asked.
**Alternatives rejected**: Report nothing, like the ruled-path keep: a CLAUDE.md edit that stood with no trace, and a reader of the packet could not tell a kept edit from an edit that never happened.
**Trade-off accepted**: One more reason constant and one more packet row.

### D8. Pre-pass text for the diff

**Choice**: Read the work-tree text of the file in `snapshot_approval_blobs`, alongside the blob id.
**Reasoning**: Lane call, 2026-11-22. No new git helper; the snapshot already opens the file list.
**Alternatives rejected**: A `blob_text` helper over `git cat-file`: a new helper for one caller, and a second way to read a blob beside `restore_blob`.
**Trade-off accepted**: The snapshot holds file text in memory for one file.

### D10. `criteria_owner` reads only the first Source line

**Choice**: Not fixed in this lane. Queued as its own item: `criteria_owner` reads every queue `Source:` line, validates each, and returns `user` when any item is `human:`-authored.
**Reasoning**: Lane call, 2026-11-22. The lane's ticket names two items; this is a third behavior change with its own test, and the scripts rules add code for a defect only when a session hit it. No session has.
**Alternatives rejected**: Fix it here: widens the ticket without the criteria owner's ruling, and couples item 2's close to a `plan_format.py` change nobody asked for. Leave it unrecorded: a mixed-author ticket with a session item's Source line first lets a session cut the user's ACs.
**Trade-off accepted**: The fail-open stays until the new item runs.

### Q1. Does the ruling retire the Owners section?

**Choice**: No. The ruling means this lane puts a new module's owner in its docstring and adds no owner line to `scripts/CLAUDE.md`. The `## Owners` section stays and item 1 protects edits to it.
**Reasoning**: Lane reading of agent-evals-c3's ruling of 2026-11-22; the same brief asks for item 1, which has nothing to protect if the section is gone.
**Alternatives rejected**: Read the ruling as retiring the section: item 1 would be moot and the brief contradicts itself.
**Trade-off accepted**: `owner_lines.py` ships with no owner line of its own.

### Q5. Fix D10 here or queue it

**Choice**: Queue it. See D10.
**Reasoning**: Lane call, 2026-11-22.
**Alternatives rejected**: In this lane: see D10.
**Trade-off accepted**: See D10.

### D9. Item 2 route

**Choice**: No prose rule. Item 2 closes on the evidence (7 of 7 lane plans print `session`; the 87-ticket survey finds no failing case) plus a deterministic replay test in `tests/scripts/test_plan_format.py`: a fixture ticket shaped like a pasted-brief lane ticket, with one `Source:` line per named queue item, prints owner `session`. The phase-1 prose bullet of the item's Done when is cut.
**Reasoning**: Ruling by agent-evals-c3 at 2026-11-22 (criteria owner `session`): close with the replay test and no prose rule; the phase-1 bullet is cut as a session ruling. It named no failing replay.
**Alternatives rejected**: Reword the phase-1 sentence with meter arms: the off arm already complies, so the meter reads no effect and W6 removes the line after 24 runs spent. Loosen `criteria_owner` to unlabeled queue paths: a user's ticket that mentions a session item would flip to `session`. Embedded-QueueItem read: self-attested authorship. Fork brief names the paths: `orchestration.md` is off-limits.
**Trade-off accepted**: A future pasted brief that names slugs and whose session writes no Source line still reads `user`; the replay test pins the shape that works, not the shape that fails.

### Q2. Glossary edits

**Choice**: This lane makes the three glossary edits in `docs/glossary.md`: "standing ruling" widens to a ruling, by the user or the orchestrating session, that covers every later reword of an AC or every owner-line edit; "approval-only file" gains the owner-line exception; "owner line" is added as a term. Recorded in the change file.
**Reasoning**: Ruling by agent-evals-c3 at 2026-11-22: a definition is not a metered rule.
**Alternatives rejected**: Leave the glossary: the code accepts a session ruling that the glossary says only the user gives, and a reader of the glossary would call the kept edit a bug.
**Trade-off accepted**: Three glossary entries change in a lane whose ticket did not name them.

### Q3. Who writes the standing-ruling line

**Choice**: agent-evals-c3's lane briefs carry the line. The change file states its exact form so a brief can copy it.
**Reasoning**: Ruling by agent-evals-c3 at 2026-11-22.
**Alternatives rejected**: A skill prose rule that writes it: needs meter arms and a skill edit outside this ticket.
**Trade-off accepted**: A lane not started from a c3 brief has no ruling and reverts as today.

### Q4. Item 2 premise

**Choice**: No failing replay exists. See D9.
**Reasoning**: Ruling by agent-evals-c3 at 2026-11-22: it has no failing replay to name.
**Alternatives rejected**: Keep hunting for one: the 87-ticket survey already covered every local plan.
**Trade-off accepted**: See D9.

### Q6. Merge order

**Choice**: `fix/toolkit-rules-nov22` merges first, then this lane. The final report names the dependency: the `claude/.claude/CLAUDE.md` sentence that lets a go-ahead cover adding or updating an owner line.
**Reasoning**: Ruling by agent-evals-c3 at 2026-11-22; it orders merges.
**Alternatives rejected**: This lane first: the code would keep an edit that the merged CLAUDE.md still forbids.
**Trade-off accepted**: This lane waits on another branch.

### Q7. Malformed ruling line stops the run

**Choice**: A malformed `Standing ruling` line in the decision log stops the review run with a critical blocker naming file and line, as a rewords ruling does today; it never only reverts the owner edit.
**Reasoning**: Ruling by agent-evals-c3 at 2026-11-22, on the criteria read-back. One grammar, loud failures.
**Alternatives rejected**: Revert the owner edit and go on: a typo in the ruling would then look like a missing ruling.
**Trade-off accepted**: The log is read at the first snapshot of every run in a repo that holds the scripts CLAUDE.md.

### Q8. Merged or reordered owner bullets

**Choice**: A merge of two owner bullets or a reorder reverts and goes back through the approval ask.
**Reasoning**: Ruling by agent-evals-c3 at 2026-11-22. Only adds and updates inside `## Owners` stand (D5).
**Alternatives rejected**: Classify a reorder as owner-lines-only: a reorder shows as a delete plus an insert and cannot be told from a drop.
**Trade-off accepted**: A tidy-up of the Owners section still asks.

### Q9. A ruling written mid-pass

**Choice**: A ruling written between the pre-pass snapshot and the pass reverts the edit, and the packet lists that revert the same way it lists every other reverted CLAUDE.md edit today. Not silent.
**Reasoning**: Ruling by agent-evals-c3 at 2026-11-22. The existing `drop_asks` row with the reverted-approval-edit reason already does this; the plan adds no second report.
**Alternatives rejected**: Tell the lane in a new message or stop line: a second report path for one case.
**Trade-off accepted**: The lane reads the packet to learn why its edit went back.

### Q10. Resume path with a saved approval ask

**Choice**: A saved approval ask for the scripts CLAUDE.md from an earlier run (the resume path) is out of scope.
**Reasoning**: Ruling by agent-evals-c3 at 2026-11-22. No session hit it.
**Alternatives rejected**: Re-judge the saved ask under the ruling on resume: code for a case no run reached.
**Trade-off accepted**: An old saved ask still waits on the user once.

### Q11. Plan review BLOCKER: change file written to the main checkout

**Choice**: `build_changes.py new` runs with `--root /home/brandon/dotfiles-review-owner-nov22/docs/changes`, the same root the rebuild uses; nothing is written to the main checkout.
**Reasoning**: Plan-reviewer finding, 2026-11-22. The branch holds the change file or AC3 fails.
**Alternatives rejected**: Create in the main checkout and copy: an edit in another checkout, which the lane rules forbid.
**Trade-off accepted**: None.

### Q12. Plan review GAP: the kept row read as a revert

**Choice**: The kept row's text is `kept_owner_line_text(path)` (no `Change:` part), and the reason reads "no approval ask is needed for an owner-line edit kept under the standing ruling by <who> at <date>", so `dropped_ask_warning`'s ", so it was dropped" refers to the ask. One test asserts the exact packet line.
**Reasoning**: Plan-reviewer finding, 2026-11-22; revised text by the architect. Reusing `approval_ask_text` would have the packet propose a revert of a kept edit.
**Alternatives rejected**: A new packet field or a `handback.py` change: a second report path for one row.
**Trade-off accepted**: The packet line still ends with "dropped", said of the ask.

### Q13. Plan review GAP: the pin cannot fail against item 2

**Choice**: AC4's evidence is a real replay, `plan_check.py owner` on this lane's own pasted-brief ticket, checked with `jq -e`; the test is regression cover for the ticket shape and is named as such. The plan states that neither can fail against item 2's premise.
**Reasoning**: Plan-reviewer finding, 2026-11-22; the fixture hand-writes the Source lines whose absence is the alleged bug. Consistent with D9 and Q4.
**Alternatives rejected**: Drop the test: the ticket shape then has no cover.
**Trade-off accepted**: The replay depends on `~/agent-evals` holding both queue items.

## Direction & Constraints

- Ruling by agent-evals-c3 at 2026-11-22: no Owners line in any CLAUDE.md this round; a module owner goes in its docstring.
- Rulings by agent-evals-c3, 2026-11-22: scripts under `claude/.claude/scripts/`, tests under `tests/scripts/` through `toolkit_paths.py`; edit in this worktree. Do not touch `claude/.claude/skills/code/**`, `claude/.claude/scripts/code/**`, `claude/.claude/CLAUDE.md`, `orchestration.md`. Every new or reworded prose rule gets rule-meter on/off arms before commit; budget 24 runs per item; meter files currently dirty from another session, so stop and message agent-evals-c3 before any edit there.
- The global exception sentence item 1 relies on exists only on unmerged `fix/toolkit-rules-nov22` (its `claude/.claude/CLAUDE.md:36`, "adding or updating" an owner line). This worktree's copy still says a go-ahead never covers a CLAUDE.md file. Merge order is Q6.
- Item 2's premise does not reproduce: all 7 lane plans of 2026-11-22 print owner `session`; a survey of every local plan ticket (87 tickets: 40 plan, 20 session, 27 user) finds no pasted-brief lane ticket reading `user`. The 27 user-owned tickets that mention a queue item are 12 copies of `plan-author-criteria/00-ticket.md` across worktrees plus tickets with no queue item.
- Real briefs name slugs, not queue paths, so the dispatch wording "names a queue item path" would miss them.
- Nothing writes a standing ruling today; `03-decisions.md` and `## Plan Deviations` are the only readers' inputs. Lane briefs from agent-evals-c3 will carry it (Q3).
- Counter-primed, not taken: post-pass ruling read; session-rulable approval asks through `phase_asks` (still asks every time); loosening `criteria_owner` to unlabeled queue paths (fails open on authority).
- No user messages in this lane; every ask goes to agent-evals-c3 with SendMessage.
