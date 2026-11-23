# Glossary

One concept, one word. Use the canonical term; never a name it lists under Avoid.

## Review loop and hand-back

### blocker

_noun_ · `is_blocker` in `claude/.claude/scripts/lib/script_utils.py`

A finding marked as one that must be fixed before the change can count as clean.

### cap-reached

_state_ · `CAP_REACHED` in `claude/.claude/scripts/review/capped_review.py`

Packet status: the loop used its round budget and findings are still open.

Avoid: "capped" (names the cap, not the status)

### class

_noun_ · `CLASSES` in `claude/.claude/scripts/review/handback.py`

The kind of problem a finding names, such as bug or smell.

### clean status

_state_ · `CLEAN_STATUSES` in `claude/.claude/scripts/review/handback.py`

A packet status that lets the work go on as reviewed.

### converged

_state_ · `STATUSES` in `claude/.claude/scripts/review/handback.py`

Packet status: the review loop ended with nothing open.

Avoid: "clean" alone (a clean status also covers deferred)

### critical-blocker

_state_ · `STATUSES` in `claude/.claude/scripts/review/handback.py`

Packet status: a blocker stopped the loop.

### deferred

_state_ · `effective_status` in `claude/.claude/scripts/review/capped_review.py`

Packet status: a cap-reached packet whose open findings may wait.

### effective status

_noun_ · `effective_status` in `claude/.claude/scripts/review/capped_review.py`

The packet status after the deferred test; the one status every reader acts on.

### finding

_noun_ · `FINDING_HEAD` in `claude/.claude/scripts/review/review_loop_findings.py`

One problem a reviewer reports at one place in the code.

Avoid: "issue" (reads as a GitHub issue)

### fix pass

_noun_ · `claude/.claude/scripts/review/review_loop_final_read.py`

One coder edit over a round's findings.

Avoid: "fix run" (a run holds several fix passes)

### fix-removed-change

_state_ · `FIX_REMOVED_CHANGE` in `claude/.claude/scripts/review/handback.py`

Packet status: fix passes removed the change under review.

### hand-back

_noun_ · `claude/.claude/scripts/review/review_loop_packet.py`

What the review loop returns to its caller when it ends.

Avoid: "handoff" (the handoff block is the input to `/code` and `/fix`)

### held file

_noun_ · `HELD_WHY` in `claude/.claude/scripts/review/review_loop_ruled.py`

A file another session is editing, so the loop leaves its findings alone.

### open class

_noun_ · `ClosureState` in `claude/.claude/scripts/review/review_loop_closure.py`

A class of finding that still has an unfixed member after the repair pass.

### packet

_noun_ · `claude/.claude/scripts/review/review_loop_packet.py`

The JSON object a hand-back carries.

Avoid: "report" (a report is a coder's reply)

### round budget

_noun_ · `ROUND_BUDGET` in `claude/.claude/scripts/review/review_loop_script.py`

The number of review rounds a loop runs before it stops as cap-reached.

### ruled-out file

_noun_ · `RULED_OUT_REASON` in `claude/.claude/scripts/review/review_loop_ruled_out.py`

A file the user put out of scope; the loop leaves its findings alone.

### setup-fault

_state_ · `SETUP_FAULT_STATUS` in `claude/.claude/scripts/review/handback.py`

Packet status: the check could not run on this machine.

## Asks and rulings

### accepted

_state_ · `ACCEPTED` in `claude/.claude/scripts/lib/ask_outcome_words.py`

Ask outcome: the ruler took the ask.

Avoid: "approved", "yes" (not outcome words the ruling command takes)

### applied

_state_ · `APPLIED` in `claude/.claude/scripts/lib/ask_outcome_words.py`

Ask outcome: accepted, and the change is already made.

### approval-only file

_noun_ · `claude/.claude/scripts/review/phase_asks.py`, `claude/.claude/scripts/review/review_loop_ruled.py`

A file a coder edits only after the user's own ruling, such as a CLAUDE.md. An owner-line edit to the scripts CLAUDE.md stands under a standing ruling that covers owner lines.

### ask

_noun_ · `ASK_CHANGE_MARK` in `claude/.claude/scripts/review/review_loop_findings.py`

A finding that waits for a ruling before any change is made.

Avoid: "question" (also a coder report's open question)

### decision log

_noun_ · `claude/.claude/scripts/lib/signoff_lines.py`

The one place a plan records rulings and sign-offs.

### held

_state_ · `HELD` in `claude/.claude/scripts/lib/ask_outcome_words.py`

Ask outcome: not ruled yet; it waits for the user.

Avoid: "parked" (not an outcome word)

### rejected

_state_ · `REJECTED` in `claude/.claude/scripts/lib/ask_outcome_words.py`

Ask outcome: the ruler declined the ask.

### relayed ruling

_event_ · `RELAYED_BY_FLAG` in `claude/.claude/scripts/lib/ask_outcome_words.py`

A user ruling given in one session and recorded by another, with the relaying session's name and the time of the user's turn, never the user's words.

### ruling

_noun_ · `RULABLE_OUTCOMES` in `claude/.claude/scripts/review/phase_asks.py`

The recorded verdict on an ask or plan impact: accepted or rejected.

Avoid: "decision" (a decision is a design choice in eng-spec)

### sign-off

_noun_ · `RULED_BY` in `claude/.claude/scripts/lib/signoff_lines.py`

A decision-log line that says who ruled and when.

### standing ruling

_noun_ · `STANDING_RULING_FORM` in `claude/.claude/scripts/lib/standing_rulings.py`

A ruling that covers every later reword of an AC (`covers: rewords`; the user's, or the orchestrating session's for a criterion the session owns) or every owner-line edit (`covers: owner-lines`; the user or the orchestrating session).

### user-only ask

_noun_ · `USER_ONLY_KEY` in `claude/.claude/scripts/lib/ask_outcome_words.py`

An ask that only the user can rule on.

## Plans and phases

### AC

_noun_ · `ID_LINE` in `claude/.claude/scripts/review/verify_common.py`

One numbered acceptance criterion of a ticket.

Avoid: "criterion" for one item (criteria names the file)

### coder packet

_noun_ · `claude/.claude/scripts/code/coder_packet.py`

The prompt built for one plan phase and handed to the coder.

Avoid: "brief" (a brief starts a lane session)

### phase

_noun_ · `claude/.claude/scripts/lib/plan_format.py`

One numbered step of a plan, built by one coder pass and checked by one review.

### plan impact

_noun_ · `PLAN_IMPACT_STATUS` in `claude/.claude/scripts/review/handback.py`

A finding whose fix changes the plan.

Avoid: "plan change" (not the status or key name)

## Checks and tree identity

### full check

_noun_ · `claude/.claude/scripts/review/full_check.py`

The repo's whole quality check, run on the final tree.

Avoid: "full suite run" (a check-only repo runs no suite)

### full-check receipt

_noun_ · `valid_receipt` in `claude/.claude/scripts/lib/full_check_receipt.py`

The record that a full check passed on one tree.

### reviewed tree

_noun_ · `record_reviewed` in `claude/.claude/scripts/lib/reviewed_tree.py`

The tree a clean review covered, so a push of that same tree passes.

### tree fingerprint

_noun_ · `tree_fingerprint` in `claude/.claude/scripts/lib/reviewed_tree.py`

The one identity of a work tree's content.

## Forks, gates and stores

### code-fork

_noun_ · `GATED_AGENT` in `claude/.claude/scripts/gates/fork_write_scope.py`

The forked agent that runs the `/code`, `/review` and `/fix` steps.

Avoid: "fork" alone (also a herdr worktree fork)

### handoff block

_noun_ · `claude/.claude/skills/_shared/handoff-block.md`

The context `/code` and `/fix` pass in when they start a run.

Avoid: "hand-back" (what the loop returns)

### ledger

_noun_ · `claude/.claude/scripts/telemetry/ledger-write`

The optional store of past session and metric rows.

### run folder

_noun_ · `PHASE_DIR_NAME` in `claude/.claude/scripts/code/code_wait.py`

The folder where a code-fork keeps its state and stop files.

### stop file

_noun_ · `STOP_FILES` in `claude/.claude/scripts/lib/stop_file_names.py`

The file a code-fork writes when it stops.

## Dotfiles

### direct-edit repo

_adjective_ · `CLAUDE.md`, section "Working with This Repo"

A repo where the session edits files itself instead of dispatching a coder.

### owner line

_noun_ · `OWNER_LINE` in `claude/.claude/scripts/lib/owner_lines.py`

A bullet under `## Owners` in the scripts CLAUDE.md that names the module owning a fact.

### template

_noun_ · `CLAUDE.md`, section "Stow Packages"

A stowed herdr or starship file that `theme-mode` turns into the real machine-local file.

Avoid: "config" alone (the generated file is the config)

## Open naming questions

1. **Orchestrating session** (49) vs **orchestrator** (108). Same role. `orchestrating session` is the global CLAUDE.md word; `orchestrator` has more uses.
2. **Lane** (399) vs **worker** (126) for the session that runs in its own worktree. `lane` is also a `--lane` option of a review run, so it is overloaded.
3. **AC** vs **criterion** (423) vs **criteria** (1184). AC names one item, criteria the file; whether `criterion` stays as prose is open.
4. **Dispatch** (160) vs **launch** (17) vs **spawn** (2) for starting a subagent.
5. **Block** (129) vs **refuse** (12) vs **deny** (1) for a hook stopping a call.
6. **Deferred**: a packet status, a plan impact deferred to phase end, and the deferred push check.
7. **Held**: an ask outcome, a held file and a held plan impact.
8. **Receipt**: full-check receipt vs closure receipt vs verify and test-audit receipts.
9. **Gate**: a hook gate, the coder gate, and a reviewer agent named as a gate.
10. **Report** for a coder's reply vs **packet** for the loop's return vs **coder packet** for the coder's prompt.
