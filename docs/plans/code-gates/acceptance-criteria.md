# Acceptance criteria

- **AC1** — A check run that fails on a shell parse or quoting error before any step of the command runs (`(eval):1: unmatched "`, with or without an `Exit code N` line) is not counted toward the quality-check cap, and a clean rerun of the same command is allowed. (Phase 1)
- **AC2** — A commit whose target repo lies under this session's scratchpad, is not the reviewed repo and was not edited by a coder dispatch passes the review commit gate; a commit in any other dirty repo is still denied. (Phase 2)
- **AC3** — A command that only quotes commit words inside a script's argument passes the commit gate, also when the script's output is piped to a program that is no code runner (`2>&1 | tail -5`); a pipe into a shell still reads as written. (Phase 2)
- **AC4** — `review/review_commit_gate.py` is under 1000 lines after the split, with no behavior change in the moved code. (Phase 2)
- **AC5** — The hand-back gate runs the gate commands set by `coder_gate.py set` in the checkout they were set in, even when the hook's cwd is another checkout, and a failing gate in that other checkout never blocks it. With no session pointer it uses the cwd. (Phase 3)
- **AC6** — A `/code` resume whose repo holds no stopped run, while this session's last relayed stop is in another run folder, is refused by `phase_start.py --resume`, naming both run folders and the relayed `To go on:` line for the recorded run; a repo whose run folder holds a stop.md, or a stop.prev.md newer than the recorded stop, resumes as before. (Phase 4)
- **AC7** — Every relayed /code stop's `To go on:` line names an absolute path: the plan path when the stop gave one, else the run's repo top. (Phase 4)
- **AC8** — `bash tests/run.sh` passes (test_rule_anchors failing on master excepted).
