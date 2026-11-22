---
type: "Change"
change_type: "fixed"
title: "code relay names the run path and phase_start refuses a resume of another checkout"
description: "code_relay.py records the session's last /code stop and puts the repo top in a To go on line that names no path; phase_start.py --resume refuses a resume in a repo with no stopped run while the session's last stop is in another run folder."
generated: {"by": "claude-opus-5-5/lane-code-gates", "at": "2026-11-21T18:44:44-06:00"}
seq: 4
kind: "fix"
components: ["script/code-relay", "script/phase-start", "script/code-stop-record", "script/script-utils"]
evidence: ["queue item code-resume-resolves-the-run-by-session-cwd-not-by: a session whose cwd moved to another checkout resumed the wrong run"]
watches: []
test: "tests/scripts/test_phase_start.py::PhaseStartTest::test_resume_in_a_repo_with_no_stop_while_the_session_stopped_in_another_names_both"
asked: ""
proof: []
unmeasured: ""
---

## Change

New `lib/code_stop_record.py` keeps one record per session: run folder, repo top, time and the relayed `To go on:` line. The per-session store is shared through `script_utils`.

`code_relay.py` records each relayed `stop.md` stop. When the stop's `/code resume` line has no absolute path right after `resume`, it inserts the run's repo top.

`phase_start.py --resume` refuses with a non-zero exit, before moving stop.md aside, when all of these hold: this repo's run folder has no `stop.md`, it has no `stop.prev.md` newer than the recorded stop, and the session's last stop is in another run folder. The refusal names both folders and prints the recorded `To go on:` line.

No SKILL.md change, per the orchestrator's ruling.

## Evidence

`test_resume_in_a_repo_with_no_stop_while_the_session_stopped_in_another_names_both` and `test_a_relayed_stop_is_recorded_for_the_session` fail without the change.

## Result

The phase gate and the full suite pass, apart from `test_rule_anchors`, which also fails on master. A no-path resume with no stop goes to the skill's step 0 and never reaches `phase_start --resume`. There, only the repo top in the relayed line covers it.

## Watch

A no-plan resume line where the fork reads the inserted repo top as a plan path, and a legitimate resume refused because the recorded stop was newer.

## Back-out

Remove the record and line rewrite from `code_relay.py`, and the refusal check from `phase_start.py`.
