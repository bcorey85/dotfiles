---
type: "Change"
change_type: "fixed"
title: "Git-only Bash hooks spawn only when the command names git or gh"
description: "The git discipline gate, the review commit gate and the deferred push check now carry `if` filters on their PreToolUse Bash entries, so a Bash call that never mentions git or gh no longer spawns three Python processes. The filters start with a wildcard, because an anchored `Bash(git *)` let wrapped forms such as `env git commit` skip the gate."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T19:14:24-05:00"}
seq: 9
kind: "fix"
components: ["script/git-discipline-gate", "script/review-commit-gate", "script/deferred-push-check"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_hook_if_filters.py::HookIfFiltersTest::test_bash_hooks_behind_an_if_filter_keep_wide_filters"
asked: ""
proof: []
unmeasured: ""
---

## Change

In `claude/.claude/settings.json`, PreToolUse `Bash` group:

- `gates/git_discipline_gate.py` runs from two handlers, `if: "Bash(*git*)"` and `if: "Bash(*gh*)"`, because it checks `gh pr create|edit` text as well as git.
- `review/review_commit_gate.py` runs from one handler, `if: "Bash(*git*)"`.
- `review/deferred_push_check.py` runs from two handlers, `if: "Bash(*git*)"` and `if: "Bash(*gh*)"`.

The other Bash hooks are unchanged. The bash safety gate still runs on every call and still blocks force pushes and pushes to main by text.

`tests/scripts/test_hook_if_filters.py` pins the rules per script.

## Evidence

Judgment, checked by three headless `claude -p` runs on Claude Code 2.1.310. A probe hook logged which `if`-filtered handlers each Bash call reached, and an unfiltered handler denied every call so nothing ran.

- `Bash(git *)` reached `cd x && git push --force`, `FOO=1 git commit`, subshells, groups, `$(git stash)`, backticks, `\git`, `"git"`, pipes, `if`/`for` bodies and `git -C`. It skipped `env git`, `/usr/bin/git`, `time git`, `command git`, `nice git`, `timeout 5 git` and `eval "git ..."`. The git discipline gate catches all of those by text today, so that rule would have opened a hole for stash, amend, attribution trailers and commits on main.
- `Bash(*git*)` and `Bash(*gh*)` reached every one of those forms, plus `env gh` and `/usr/bin/gh`. They skipped `echo`, `ls`, `npm test`, `python3 ...` and `rg`.
- Two handlers with the same command and different `if` rules are not merged: a command naming only gh reached the gh handler, and one naming both ran the hook twice.

## Result

The gain is CPU only: about 30 ms of Python per hook per Bash call that names neither git nor gh, three hooks each. No wall-clock gain while the unfiltered bash safety gate bounds the event. A command that names both git and gh runs the git discipline gate and the deferred push check twice; both are read-only checks, so a double deny repeats the message and changes nothing else.

## Watch

None. No intake number reads hook CPU. The test keeps the rule.

## Back-out

Delete the `if` lines and the duplicate `*gh*` handlers from the PreToolUse Bash group.
