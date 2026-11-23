# Acceptance Criteria — review-owner-1122

> Written before implementation. The closing Verify phase reconciles these
> against the test suite.

Ticket item 2's first "Done when" bullet (a phase-1 prose or fork-brief change with rule-meter arms) is cut by the ruling of agent-evals-c3 on 2026-11-22 (ledger D9/Q4): item 2 closes on evidence with a replay test and no prose rule. It is not an open criterion.

## Item 1 — ticket criteria

- **AC1** — `review_loop_ruled.py` keeps an edit to `claude/.claude/scripts/CLAUDE.md` whose only changed lines are owner lines (a pointer to the module that owns a fact) when the run's decision log records a session ruling for it, and still reverts every other CLAUDE.md edit.
- **AC2** — A test under `tests/scripts/` fails before the change and passes after it, for both the kept owner line and the reverted non-owner edit.
- **AC3** — Change file in `~/dotfiles/docs/changes/` with kind fix naming that test.

## Item 2 — ticket criterion

- **AC4** — A replay of a pasted-brief lane prints owner `session`.

## Derived from the ticket's intent

- **AC5** — After a review fix pass adds or updates an owner bullet under `## Owners` in the scripts CLAUDE.md with a session ruling on record, the edit is still in the file and the user is not asked about it.
- **AC6** — A kept owner-line edit is reported in the review packet as kept under the named ruling, so it is visible and not silent.
- **AC7** — A fix-pass edit to the scripts CLAUDE.md that mixes an owner line with any other change (prose, another section, a removed or merged bullet, a reordering, a renamed heading) is reverted whole, as today.
- **AC8** — An owner-shaped edit to any other CLAUDE.md, including another `scripts/CLAUDE.md` path, is reverted as today.
- **AC9** — With no session ruling on record, or a ruling that covers only rewords, or no plan in the run, an owner-line edit is reverted as today.
- **AC10** — A ruling line the fix pass itself writes does not make that same pass's owner-line edit stand.
- **AC11** — A decision-log ruling line with `covers: owner-lines` is accepted, and every existing `covers: rewords` line and its consumers behave as before.
- **AC12** — A malformed `Standing ruling` line names its file and line instead of being skipped.
- **AC13** — If the scripts CLAUDE.md cannot be read when the edit is judged, the edit is reverted as today, not kept.
- **AC14** — An owner-line edit the pass committed stays committed and stands.
- **AC17** — The pasted-brief replay uses a ticket shaped like this lane's own (two Source lines, pasted queue items) and fails if the owner reads `user`.

## Manual only

- **AC15** — The module that owns the owner-line format states its ownership in its own docstring, and no line is added to any CLAUDE.md for it. Reason: text presence; the branch diff shows it, and no test asserts prose.
- **AC16** — The glossary names an "owner line" and its "approval-only file" and "standing ruling" entries cover the session-ruled owner-line case. Reason: prose the reader judges; Phase 4's `rg` checks only prove presence.
