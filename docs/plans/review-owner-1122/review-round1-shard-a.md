# Plan review, round 1, shard a (whole plan)

DUCK     Phase 1: adds `changed_line_ranges` to `lib/protected_lines.py` and rewrites `changed_stretches` on top of it. Adds a new `lib/owner_lines.py` holding the path constant, the `Owners` heading, the `OWNER_LINE` regex and `owner_lines_only(before, after)`, with case-table tests and a test against the real file.
DUCK     Phase 2: makes the `covers` group in `standing_rulings` accept `rewords|owner-lines`. Adds `first_ruling_covering` and `owner_line_ruling`, and `reword_ruling` keeps its behaviour.
DUCK     Phase 3: `snapshot_approval_blobs` reads the pre-pass text of the scripts CLAUDE.md and the owner-lines ruling. A new `keeps_owner_line_edit` step in `ask_for_approval_only_edits` skips the revert and files a "kept" row in the dropped asks. Tests run on a temp git repo.
DUCK     Phase 4: adds a test that pins item 2 using a ticket that already has Source lines, three glossary edits, and a change note made with `build_changes.py new`.
DUCK     Phase 5: the `/close-branch` review pass and the full suite.

BLOCKER  Phase 4 §3, change file: the command writes the note into the main `~/dotfiles` checkout, not this worktree, so the branch never holds the change file.
         Evidence: the plan says `build_changes.py new "…" --by … --root /home/brandon/dotfiles/docs/changes` and then "the lane's worktree copy is edited and the pages rebuilt with … --root /home/brandon/dotfiles-review-owner-nov22/docs/changes". `build_changes.py new --help` shows `--root ROOT` as the place the unfilled `<date>-<slug>.md` is written.
         Reading: a coder who runs the command as written creates `/home/brandon/dotfiles/docs/changes/notes/2026-11-22-<slug>.md` in the master checkout. No "worktree copy" exists to edit, so the coder either edits a file in another checkout (the lane rules forbid this) or has to copy it by hand. The `rg -l 'covers: owner-lines' docs/changes/notes` check runs in the worktree and fails. AC3 is not met on the branch. The `new` call needs `--root /home/brandon/dotfiles-review-owner-nov22/docs/changes`, the same root the rebuild step already uses.

GAP      Phase 3 / AC6: the "kept" row tells the reader the edit was reverted, or proposes a revert, while the edit was kept.
         Evidence: `keeps_owner_line_edit` files `parse_finding(approval_ask_text(path))`. `approval_ask_text` (`review_loop_ruled.py:61-62`) reads "A fix coder edited `…`, which needs the user's approval. Change: " + `approval_change(path)`, and `approval_change` gives `CHANGE_PREFIX = "revert the fix coder's edit to \`"` (`review/approval_asks_store.py:16,25`). `handback.dropped_ask_warning` (`handback.py:474`) prints `f"{drop_reason}, so it was dropped: {text!r}"`.
         Reading: the packet line becomes "kept under the standing ruling by X at D, so it was dropped: 'A fix coder edited …, which needs the user's approval. Change: revert the fix coder's edit to …'". AC6 asks for the edit to be "reported … as kept". The row it gets says "dropped" and proposes a revert. The plan names no other text for the kept row, so a coder will reuse `approval_ask_text` exactly as written.

GAP      Phase 4 §1 / AC4, AC17: the pin cannot fail against the defect item 2 describes.
         Evidence: the ticket's defect is that "eng-spec phase 1 writes Source only when the ticket is a queue file". The pin's fixture writes "two `Source: ~/agent-evals/queue/<slug>.md` lines" by hand and then asserts `owner == CRITERIA_OWNER_SESSION`. `criteria_owner` (`lib/plan_format.py:1542-1546`) returns from the first queue Source line before it reads anything else, and the existing `test_a_ticket_copied_from_a_queue_item_a_session_wrote_is_session_owned` (`tests/scripts/test_plan_format.py:513`) already pins that path.
         Reading: the test passes whether or not phase 1 ever writes a Source line, because the fixture supplies the very lines whose absence is the bug. It replays nothing of phase 1. The real evidence that item 2 does not reproduce is the 7-of-7 / 87-ticket survey in Constraints, plus `plan_check.py owner` on this lane's own plan, which I ran: it prints `"owner": "session"`. AC4 says "prints owner session", but the pin calls `plan_format.criteria_owner` rather than the `plan_check.py owner` command. The plan should say the pin is regression cover only and point to the survey as the evidence for AC4. As written, it presents a test that cannot fail as the replay.

NIT      Phase 3 tests: `SCRIPTS_MD` is defined in `test_owner_lines.py` (Phase 1), but `OwnerLineEditTest` writes "Phase 1's `SCRIPTS_MD`". This can be read two ways: import it across test modules, or copy the literal. Name one.

NIT      Phase 3 tests: every `coder_pass` passes `findings=[]`. AC5's real-world case, a reviewer finding located on `claude/.claude/scripts/CLAUDE.md`, is never exercised. One subcase with a finding on that path would show that `ask_for_wanted_changes` files no user-only ask for a kept path (it should not, since the path is not in `reverted`).

NIT      Phase 4 §3: the `test:` value uses `path::Class::test` joined with `; `. The validator only checks that `::` is present (`build_changes.py:393`). The existing notes mostly use `path::Class.test_name`, and only 3 notes hold `;`. It passes as written.

NIT      Constraints: "All 72 owner bullets ever added" does not match the in-tree history. `git log -p -- claude/.claude/scripts/CLAUDE.md` shows 53 distinct added bullets. The 45 under Owners all match `OWNER_LINE`, and the 8 that fail are non-Owners prose bullets. The other 19 may come from history under an earlier path. The regex holds on everything I could reach.

Claims settled (all hold unless listed above):
- `review_loop_ruled.py` is 665 lines.
- Imports are at lines 10-46 and the findings import at 28-41.
- `init_ruled_state` is at 197-225, with `approval_blobs` at 214.
- `standing_reword_ruling` is at 340-349.
- `ask_for_approval_only_edits` is at 366-393, with the ruled `continue` at 383-384.
- `revert_approval_edit` is at 460.
- `snapshot_approval_blobs` is at 502-522.
- `drop_asks` dedupes (232-235).
- `REVERTED_APPROVAL_EDIT_REASON` is at `review_loop_findings.py:388`.
- `review_loop_script.py:319` sets `self.plan`; the snapshot is at 573 and the ask step at 591.
- `review_loop_partial_fix.py:213` is the only other caller (2 production callers).
- `review_loop_packet.py:59` builds the dropped row.
- `review_loop_main.py:213-215` catches `PlanFormatError` and stops with critical-blocker.
- The only `reword_ruling` consumers are `plan_check.py:48`, `review_fix_plan_impacts.py:256` and `review_loop_ruled.py:349`.
- In `standing_rulings.py`, line 15 is `COVERS_REWORDS`, line 16 is the form, 18-20 is the regex and 60-65 is `reword_ruling`.
- `protected_lines.changed_stretches` is at 24.
- `StretchHelpersTest` is at 17.
- In `test_plan_format.py`: `STANDING_LINE` at 782, the malformed table at 815-831, `CriteriaOwnerTest.queue_item(frontmatter_body, slug=)`, and the test at 627-632.
- In `test_review_loop_ruled.py`: init at 929-931, `git_run` at 943-944, `ApprovalAskTextTest` at 1111, plus `approval_host`, `Host` (has `plan`, calls `init_ruled_state`) and `GIT_ENV`.
- `toolkit_paths.LIB_DIR` and `REPO_ROOT` exist.
- Glossary: 145 is the `approval-only file` code ref and 147 is that entry's empty line (the definition is at 146), 201 is the standing-ruling definition, and 313 is `### template` under `## Dotfiles` at 305.
- No decision-log line in this plan folder starts `Standing ruling`.
- All 26 current Owners bullets match `OWNER_LINE`.
- `owner_lines.py` and `test_owner_lines.py` do not exist yet.

VERDICT: NEEDS CHANGES (1 blocker, 2 gap)

## Resolution (round 1, STANDARD max 1 round)

- BLOCKER: fixed in Phase 4 §3 (worktree root); ledger Q11.
- GAP kept row: architect's revised Phase 3 text (`kept_owner_line_text`, new reason wording, exact packet-line test); ledger Q12.
- GAP pin: architect's revised Phase 4 §1 (real replay with `jq -e`, test as regression cover, limit stated); ledger Q13.
- NITs: all four fixed in the spec (import named, case (f) with a finding on the path, `path::Class.test` form, history count 53/45/8).
