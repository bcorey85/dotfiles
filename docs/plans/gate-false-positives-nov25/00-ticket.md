# gate-false-positives-nov25: nine gate and hook false positives or wrong messages

Source: ~/agent-evals/queue/staged-claim-gate-false-positive-on-pending.md
Source: ~/agent-evals/queue/staged-claim-gate-flags-first-person-promises.md
Source: ~/agent-evals/queue/permission-question-gate-misses-an-ask-to-add-a.md
Source: ~/agent-evals/queue/rg-path-gate-rewrites-a-no-path-rg-instead-of.md
Source: ~/agent-evals/queue/push-gate-sends-a-committed-change-to-a-review.md
Source: ~/agent-evals/queue/test-run-hook-tells-macos-sessions-to-use-systemd.md
Source: ~/agent-evals/queue/staged-claim-stop-gate-fires-on-a-line-that-names.md
Source: ~/agent-evals/queue/push-gate-stays-blocked-after-a-capped-review.md
Source: ~/agent-evals/queue/review-loop-write-full-check-tree-so-a-capped.md

## 1. staged_claim_gate false positive on pending background agents

### Context
The Stop hook `staged_claim_gate.py` blocked a turn-ending message that said a ranked list would follow. The step it depended on (several background Agent dispatches) was started earlier in the same turn; the list can only come after their completion notices. The gate read "I'll bring back" as an unstarted step.

### Done when
The gate treats a promised follow-up as started when the same turn launched background agents (Agent calls with run_in_background) that the follow-up waits on, and a regression case covers it.

## 2. staged_claim_gate flags first-person promises inside a drafted message for the user

### Context
The user asked for a reply to paste to a reviewer. The draft said "I am fixing X" in the user's voice. The Stop hook read those lines as the assistant promising work and blocked the turn end, forcing an extra turn.

### Done when
The gate skips text inside a fenced or delimited draft block (or a message the turn labels as a draft for the user), and a test covers a drafted reply with first-person promises passing.

## 3. Permission-question gate misses an ask to add a tracker link

### Context
The main session ended a reply asking whether to add a link between two tracker issues. The Stop gate read it as a permission question for a reversible step and told the session to take the step now. A tracker write leaves the machine and is visible to the team, so the ask was required.

### Done when
A test in the gate's suite asks "Shall I add a Jira link from A to B?" and "Want me to label the ticket?" and both pass as outward asks; the current local-step cases still block. Fails before the change.

## 4. rg path gate rewrites a no-path rg instead of denying it

### Context
The main session ran rg with no path twice in one session. Each time the gate denied it and printed the exact fixed command, and the session re-sent it: two wasted round trips for a fix the gate already computes.

### Done when
A gate test feeds a Bash call with rg and no path and gets back an allow decision with updatedInput holding the command with the dot path appended; a no-path rg reading from a pipe stays allowed unchanged. Fails before the change.

## 5. Push gate sends a committed change to a review that sees nothing

### Context
After a commit, the push gate refuses the push because code changed since the last review, and its message says to run `/review` on the branch. With no base argument, `/review` scopes to working-tree changes against HEAD. After the commit that scope is empty, so it stops with "no changes".

### Done when
The gate's refusal names the base to review from (the last reviewed commit), or `/review` with no base falls back to the commits the gate counts as unreviewed.

## 6. Test-run hook tells macOS sessions to use systemd-run

### Context
The PreToolUse Bash hook that blocks a foreground full test suite tells the session to rerun inside `systemd-run --user --scope ... MemoryMax=8G`. On darwin there is no systemd, so the named approved path cannot run.

### Done when
The hook's message names a cap command that works on the host OS (or names run_in_background alone on darwin).

## 7. Staged-claim stop gate fires on a line that names a check of what is staged

### Context
A reply described a lane's pre-commit feature ("checks the skill list against what is staged"), and an earlier reply listed another worktree's staged files. Both times the Stop hook blocked, saying the index is empty. Neither reply claimed the session's own repo had staged files.

### Done when
A test in tests/scripts/ passes the reply "It checks the skill list against what is staged." and a reply that names another worktree's staged files by its path, and still blocks "I staged the change." with an empty index. It fails before the fix and passes after.

## 8. Push gate stays blocked after a capped review whose leftovers the caller fixed by hand

### Context
A review stopped at its round cap with only plan-text drift left. The caller fixed the plan by hand and committed it. The push gate still refused with "code changed since the last review": a capped review logs no pass.

### Done when
A test shows the gate lets a push through when the last review is logged, its only open findings are plan-file text, and the commits since then touch only the plan directory. The same test shows the gate still blocks a push after a code commit.

## 9. Review loop: write full_check_tree so a capped review with a passed full check reads as deferred

### Context
capped_review.effective_status requires packet['full_check_tree'] to equal the work tree's fingerprint, and no loop writer fills that field. A cap-reached review with no blocker, no open class and a passed full check still printed cap-reached.

### Done when
the loop writes full_check_tree from the tree it checked, a test gives effective_status such a packet and gets deferred, and bash tests/run.sh passes.
