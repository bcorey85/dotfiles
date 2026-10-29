---
type: "Change"
change_type: "removed"
title: "Retire the spec criteria lint"
description: "The eng-spec finalization step no longer runs spec-criteria-lint.sh, and the script is deleted. Its one check, verification paths that no phase creates, was wrong on every report it made."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T22:28:55-05:00"}
seq: 24
kind: "behavior"
components: ["script/spec-criteria-lint", "skill/eng-spec", "shared/escape-ratchet"]
evidence: ["work incident", "census"]
watches: []
---

## Change

- `skills/eng-spec/phases/6-finalize.md`, step 16b: the "Static lint" bullet is deleted. The falsifiability run and the batch rule stay.
- `skills/_shared/escape-ratchet.md`, rung 5: a `check` is now a falsification-sweep line only. The lint is no longer a place to add a plan-text rule.
- The lane bundle deletes `scripts/spec-criteria-lint.sh` and drops its name from the `guard=check` comment in `scripts/log-escape`. The script had no installed test.

## Evidence

- Work incident: on one finalization run, the lint gave 12 findings and exit 1. All 12 were false. The match used `grep -Fx`, so a `(new)` file line never matched the same file as an absolute path in a command, and paths were cut at `.claude/`.
- Census: of 15 reports from the lint, 0 were correct. The installed script held only the orphan-path check, so nothing else is lost.

## Result

Each finalization runs one less command, and the user no longer resolves false lint findings before Phase 7. The falsifiability run still runs each read-only verification command against the tree. A command that names a file no phase creates fails there.

## Watch

None. The intake has no metric for lint findings or for finalization questions to the user.

## Back-out

Restore the script from git history, the "Static lint" bullet in step 16b, and the lint clause in rung 5 of the escape ratchet.
