# Stop hook blocks a reply whose next step waits on another session or a date

Source: ~/agent-evals/queue/stop-hook-blocks-a-reply-whose-next-step-waits-on.md

## Context

On 2026-11-27 the stop hook that checks for promised-but-unstarted steps blocked three status replies in a row in one orchestrating session. Each reply named a next step that waited on someone else: a weekly scan not due until a later date, and a scenario repoint waiting for a peer session to confirm a merge. The session then had to write a second reply, and the user reported they could not see what the session had written. A reply that names who acts next and what it waits on is the status format the repo asks for, so the gate fights the rule.

Lets the toolkit delete: nothing.

## Done when

- A reply whose future step is gated on a named other party or a date (for example 'once X confirms', 'after Nov 29', 'when the lane reports') passes the gate; a test in tests/scripts covers each form.
- A bare first-person promise with no gate ('I'll run the suite next') still blocks.

## Lane brief additions (agent-evals-74, 2026-11-27)

This worktree starts at weekend-toolkit-fixes-v2 (be9a5807d). The user asked on 2026-11-27 that a Stop hook never hide a reply from them. Today, when a Stop hook blocks (decision block), the turn goes on, so in focus mode the user sees only the agent's next message and never the reply the hook stopped. The user lost three status replies this way, all false hits of claude/.claude/scripts/gates/staged_claim_gate.py.

Two fixes, one change file each (`python3 ~/agent-evals/bin/build_changes.py new ... --root docs/changes`):
1. Every Stop hook in claude/.claude/settings.json that can block (staged_claim_gate.py, format_changed.py, and any other you find) puts the blocked reply's full text in the hook output's `systemMessage`, so the user sees it. Check the Claude Code hooks docs (WebSearch) for the Stop output fields and how `systemMessage` shows, and put the doc link in the change file. Put the shared part in one helper in claude/.claude/scripts/lib/ that each Stop hook calls. Kind `user-rule`, date 2026-11-27, paraphrase the ask; never quote the user. It is hook code, not prompt text, so no rule-meter run; say so in `unmeasured`.
2. Build ~/agent-evals/queue/stop-hook-blocks-a-reply-whose-next-step-waits-on.md (read it in full; its "Done when" is the acceptance criterion): a future step gated on another party or a date passes. Kind `fix`, naming the file::test that fails before and passes after.
Measure each changed hook's median time beside a bare Python start and put both in its change file.

## Comments

none
