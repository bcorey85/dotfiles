---
type: "Change"
change_type: "changed"
title: "Toolkit scripts sorted into code, review, gates, telemetry, lib and tools folders"
description: "The 52 flat scripts in ~/.claude/scripts moved into six folders by concern. Hook commands, imports and logic are unchanged; only paths changed."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-24T15:09:38-05:00"}
seq: 11
kind: "behavior"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: ""
unmeasured: "A pure move. Every hook command, import and printed text keeps its behavior, so no intake number moves. The gain is finding a script by concern, which no stream counts."
---

## Change

`claude/.claude/scripts/` now has `code/` (code-step, coder gate, coder packet), `review/` (review fix, hand-back, review gates, verify helpers), `gates/` (the other hook gates), `telemetry/` (loggers, ledger-write, telemetry switch), `lib/` (hook_input, script_utils, shell_command, plan_format, _kv.sh) and `tools/` (branch-base, repo-name, resolve-task-dir, notify, rule-anchors, claude-doctor). The three generated security hooks stay at the top.

Imports stay flat: each script puts its own folder, `lib/` and any other folder it imports from on `sys.path`, from the real path of its own file, so a symlink at an old flat path still imports. A package layout was rejected because a folder named `code` shadows the stdlib `code` module, and flat module names keep test patching on one module.

`settings.json`, skills, agents, the opencode port and deny list, the pi settings, the omp bridge, `claude-bg`, `ruff.toml`, `tests/run.sh`, `docs/rule-anchors.md` and the tests name the new paths. agent-evals `bin/renamed_scripts.existing_script_path` also finds a script in the flat folder, for a machine that has not pulled the move.

## Evidence

User decision on 2026-10-24: build the folder layout now, not when the folder grows.

## Result

Unmeasured. See `unmeasured`.

## Watch

None.

## Back-out

Revert the merge commit. `settings.json` reverts with it.
