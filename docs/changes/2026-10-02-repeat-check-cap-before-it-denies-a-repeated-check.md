---
type: "Change"
change_type: "fixed"
title: "The repeat-check cap now allows a repeated check when any changed or untracked file is newer than the last run"
description: "Repeat-check cap: before it denies a repeated check, it allows the check if any changed or untracked file in the repo is newer than the last run, so writes through the shell or a script count as edits."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-02T00:00:00-05:00"}
seq: 12
kind: "fix"
components: ["script/quality-check-cap"]
evidence: ["judgment"]
watches: []
---

## Change

Repeat-check cap: before it denies a repeated check, it allows the check if any changed or untracked file in the repo is newer than the last run, so writes through the shell or a script count as edits. It records no run when the check failed by timeout or interrupt

## Evidence

judgment

## Result

In one bench ticket run, these two false denials caused 3 coder stops: one timed-out typecheck counted as a run, and two cases of edits through the shell or a script went unseen. Seeded hook test: 11 of 11 cases pass. Only the 4 targeted cases change from deny to allow. Work logs cannot size it, because the cap does not log its denials. Cost: one `git ls-files` call, only on the deny path.

## Watch

—

## Back-out

restore the script from git
