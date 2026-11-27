# code-gates-1123: four /code and gate defects

Source: ~/agent-evals/queue/code-fork-dispatched-a-coder-and-returned-with-no.md
Source: ~/agent-evals/queue/announced-step-stop-gate-fires-while-a-background.md
Source: ~/agent-evals/queue/inline-python-heredoc-that-rewrites-an-untracked.md
Source: ~/agent-evals/queue/quality-check-cap-treats-a-run-piped-into-rg-as.md

## 1. code fork dispatched a coder and returned with no review loop on a plain task

### Context
2026-11-23, agent-evals: a /code run on a plain task (no plan file, a queue item) made four tool calls: one read, one coder dispatch, one code_wait, one git status. It never ran code_step.py or code_review_start.py, and its report said it did not run lint. The diff carried four new lint errors and a regression (old unfilled change notes no longer read as unfilled); the orchestrating session found both by hand. An earlier run in the same session on a similar plain task did run the review loop.

### Done when
A check fails a /code fork's hand-back when the run folder holds no review packet for the phase (or a recorded reason the step allows), and passes when the review ran. A test in tests/scripts pins both cases.

## 2. Announced-step stop gate fires while a background shell and a subagent are running

### Context
Right after the gate went live, a turn ended with a status saying a suite and an agent were running. Both had started in that same turn: a background `tests/run.sh` shell and a forked subagent. The gate still sent the turn back with "nothing started". Every status turn while work runs in the background pays one extra turn.

### Done when
A test: a transcript where the turn launched a `run_in_background` Bash call and an Agent call, and the final text says "is running", passes the gate. A turn that launched nothing still gets sent back.

## 3. Inline python heredoc that rewrites an untracked source file passes every gate

### Context
In one text-scout build, the coder made its first edit batch in round 2, and again in round 3, with `cd bin && python3 - <<'EOF'` doing `open(p).read()` ... `.replace(...)` ... `write`. Neither run was blocked. The target, a new scout script, is untracked. The 2026-10-27 fix only denies inline code that writes a tracked file, so a branch's new files are open to the form the coder rule bans.

### Done when
A hook test runs `cd <repo>/bin && python3 - <<'EOF'` with an open(...).write on an untracked .py file inside the repo. It fails before the fix (the call is allowed) and passes after (the call is denied, pointing to Edit or Write).

## 4. quality-check-cap treats a run piped into rg as seen in full, so the one redirected rerun is denied

### Context

2026-11-22, agent-evals main session: a unit test run piped into `rg '^(Ran|OK|FAILED)'` showed one failure and no
failure text. The rerun redirected to `/tmp/check.log`, the form the deny itself names, was denied too, because
`OUTPUT_FILTER_START` in `~/.claude/scripts/gates/quality_check_cap.py` (line 92) matches only tail, head and grep.
The session had to stop with an unread failure.

### Done when

A test records a check piped into `rg` (and `rg -A`) as cut, then allows one rerun redirected to a file; the test
fails while `OUTPUT_FILTER_START` lists only tail, head and grep.
