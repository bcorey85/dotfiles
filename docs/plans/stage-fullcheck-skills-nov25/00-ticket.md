# Stage, full check and skill fixes: five queued items

Five queue items, each copied verbatim below. The Done-when lines of each are the acceptance criteria.

---

# stage --run aborts on an already-staged deleted file

Source: ~/agent-evals/queue/stage-run-aborts-on-an-already-staged-deleted-file.md

---
type: "QueueItem"
title: "stage --run aborts on an already-staged deleted file"
description: "Let /stage's run mode handle a deleted file that is already staged instead of aborting the whole queue build."
generated: {"by": "process:orchestrator", "at": "2026-11-24T19:05:04-06:00"}
kind: "chore"
status: "queued"
rank: 985
blocked_by: []
source: "skills/stage stage.mjs"
components: ["skill/stage"]
---

## Context
At a /code phase end, `stage.mjs --run` aborted because one file in the change set was a deletion already staged in the index. The phase had to re-run it with `--no-stage`, so nothing was auto-staged and the user had to sort out a partly staged index by hand.

## Done when
- `--run` treats an already-staged deletion as staged and goes on with the rest of the queue.
- A test covers a change set with a staged deletion beside unstaged edits.

---

# code review loop backend suite regression on frontend diff

Source: ~/agent-evals/queue/code-review-loop-backend-suite-regression-on.md

---
type: "QueueItem"
title: "code review loop backend suite regression on frontend diff"
description: "Stop /code's review loop running the backend suite on frontend-only diffs again, and let a brief turn a gate off."
generated: {"by": "claude-code/opus-5-5", "at": "2026-11-24T09:39:00-06:00"}
kind: "method"
status: "queued"
rank: 985
blocked_by: []
source: "skills/code"
components: ["skill/code"]
not_dup: "The 2026-11-19 fix was meant to run only the touched suite, but on 2026-11-24 a frontend-plus-plan-doc diff still ran the backend suite. This item covers that regression and adds a caller switch to turn the gate off."
---

## Context
The queue item review-full-check-ignores-frontend-only-changes was closed on 2026-11-19, but the gap has come back. On 2026-11-24 a phase diff touched only frontend source and a plan markdown file under docs/plans, and the loop's full check still started the Django test suite. The plan doc may be what makes the loop see a backend change. The user had asked for no backend suites, and the caller could not switch the gate off. The fork killed the suite, which killed the loop before it returned its packet.

## Done when
- A diff of frontend files plus plan docs runs no backend suite.
- A brief can turn off a named gate. The loop records it as skipped and still returns its packet.

---

# lane-status reports each lane branch merged or ahead and who it reports to

Source: ~/agent-evals/queue/lane-status-reports-each-lane-branch-merged-or.md

---
type: "QueueItem"
title: "lane-status reports each lane branch merged or ahead and who it reports to"
description: "Orchestrating sessions read each lane's merge state and report-to session from one allowed script, so they stop writing shell loops that stop for a permission prompt the user must click."
generated: {"by": "claude-opus-5-5/main", "at": "2026-11-25T13:47:41-06:00"}
kind: "live-edit"
status: "queued"
rank: 9002
blocked_by: []
source: "scripts/.local/bin/lane-status"
components: ["script/lane-status"]
not_dup: "the refactor and code skills hold no lane git-state report; this adds one to lane-status"
---

## Context
An orchestrating session checked three lanes' state with a shell for-loop over branch names: merged into origin/master or N commits ahead, plus `reports_to` from each lane file. Claude Code cannot check a command that holds a shell variable, so it asked the user to approve the loop. The user reported being prompt-spammed by these checks (2026-11-25). lane-status today reports agent state, memory and scratch space, but not a lane's git state or who it reports to, so sessions rebuild that by hand.

## Done when
`lane-status --git` (or the default output) prints, per open lane: branch, merged or N ahead / M behind origin's default branch, dirty file count, and `reports_to`. A test in tests/scripts/ pins each field on a fixture lane. lane-status has an allow rule so the call never prompts.

Deletes: the hand-written per-lane git status loops orchestrating sessions run.

---

# fix skill run with no args finds no findings because its fork cannot read the conversation

Source: ~/agent-evals/queue/fix-skill-run-with-no-args-finds-no-findings.md

---
type: "QueueItem"
title: "fix skill run with no args finds no findings because its fork cannot read the conversation"
description: "The fix skill gets its findings on the first call instead of stopping empty and needing the user to rerun it with the findings pasted in."
generated: {"by": "claude-opus-5-5/main", "at": "2026-11-25T00:30:23-06:00"}
kind: "chore"
status: "queued"
rank: 985
blocked_by: []
source: "claude/.claude/skills/fix/SKILL.md"
components: ["skill/fix", "agent/code-fork"]
---

## Context
The fix skill runs as `context: fork` on the code-fork agent, but its description and step 1 still list "the conversation" as a findings source. A forked run does not see the main session's conversation. In one session the user ran the fix skill with no arguments after a review in the main session had listed the findings. The fork found nothing to fix and stopped. The user had to run it again with the findings pasted in, which cost a full turn. The toolkit-writing check 1 says a fork skill's description must carry every instruction the main session needs. Here the missing instruction is that the main session must pass the findings in the args.

## Done when
- The fix skill description tells the caller to pass the findings in the args. It no longer lists the conversation as a source the fork reads.
- A no-args run stops at once with one line asking for the findings. It does not start a loop.
- A test or a skill-lint check fails when a `context: fork` skill's description names "the conversation" as an input source.

---

# Make /adr a run step at branch end, not a pointer

Source: ~/agent-evals/queue/make-adr-a-run-step-at-branch-end-not-a-pointer.md

---
type: "QueueItem"
title: "Make /adr a run step at branch end, not a pointer"
description: "Branch end runs /adr as a step, so the plan dir is removed and the ADR written without the user asking."
generated: {"by": "claude-code/opus-5-5", "at": "2026-11-24T13:39:55-06:00"}
kind: "method"
status: "queued"
rank: 985
blocked_by: []
source: "claude/.claude/skills/verify-branch/SKILL.md"
components: ["skill/verify-branch", "skill/close-branch", "skill/adr"]
---

## Context
verify-branch's Clean route ends with "After the PR exists, /adr" and close-branch lists /adr only on its Next line. Both are forward pointers, not run steps, so a session finishes the review packet and push and never writes the ADR or deletes the task dir. The user has to remind the session each branch.

## Done when
- The branch-end route makes /adr a numbered step that runs once the PR exists (or prints a blocking reminder until the ADR is committed and the task dir gone).
- A branch whose PR exists and whose task dir still exists is reported as not finished.
