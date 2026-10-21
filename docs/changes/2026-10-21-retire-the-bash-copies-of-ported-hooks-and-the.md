---
type: "Change"
title: "Retire the bash copies of ported hooks and the port workspace"
description: "The installer deletes the bash copy of 20 hooks whose Python port settings.json runs, then deletes the port workspace ~/dev/evals/hookport/. Script prose stops naming the old .sh files."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T00:31:50-05:00"}
seq: 2
components: ["script/agent-foreground", "script/agent-model-guard", "script/batch-reads-nudge", "script/calibration-guard", "script/calibration-refs-guard", "script/claudemd-linecount", "script/comment-bloat-gate", "script/dead-prose-gate", "script/emit-orchestration", "script/format-changed", "script/git-discipline-gate", "script/log-agent-usage", "script/log-skill-use", "script/quality-check-cap", "script/review-commit-gate", "script/shell-write-gate", "script/spec-budget-gate", "script/stale-citation-gate", "script/test-edit-telemetry", "script/warn-skip-hooks", "script/claude-doctor", "script/review-gate-mark"]
evidence: ["judgment", "tests"]
watches: []
---

## Change

- The installer deletes the `.sh` copy of 20 hooks. Each one has a `.py` port, and `settings.json` runs only the port. The installer refuses a `.sh` file that `settings.json` names or that has no `.py` twin.
- After the deletes, it deletes `~/dev/evals/hookport/`, the port workspace with its parity harness (50M). It skips this step when it refuses any delete.
- `claude-doctor.sh` and `review-gate-mark` name the `.py` hooks. Eight ported hooks lose the "Port of X.sh" sentence in their docstring.
- The opencode copy of `mutation-tester.md` loses its sentence about `calibration-guard.sh`. Opencode does not run that guard, and the Claude copy already dropped the sentence. A test comment stops naming the parity harness.
- These `.sh` files stay: the three safety hooks that have no port, `telemetry_enabled.sh` for the bash writers, four tool scripts with no port (`resolve-task-dir`, `spec-criteria-lint`, `rule-anchors`, `claude-doctor`), and herdr's own hook.

## Evidence

Judgment: the `.sh` copies run nowhere. They stayed only as the back-out for the port. A reader who finds one can edit or cite the wrong file. A skill line named `calibration-guard.sh` until 2026-10-21.

Tests: the tests of each port are in `~/dotfiles/tests/scripts/` and pass against the installed `.py` files.

## Result

Installed 2026-10-21 with the sign-off install bundle. The installer runs the full test suite before it deletes the port workspace.

## Watch

None. A deleted hook that something still calls fails at its next call. No work-log number measures that.

## Back-out

Restore the `.sh` files from the dotfiles history, and put their names back in `settings.json`. The port workspace is not in git, so its parity harness is gone after the delete.
