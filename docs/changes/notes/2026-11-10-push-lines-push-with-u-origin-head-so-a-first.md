---
type: "Change"
change_type: "changed"
title: "Push lines push with -u origin HEAD so a first push works"
description: "The global push rule now ends every push line with git -C <repo> push -u origin HEAD in place of a bare git push, which fails on a brand-new branch with no upstream."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-10T19:00:00-06:00"}
seq: 6
kind: "user-rule"
components: ["rule/global-claude-md"]
evidence: ["user rule"]
watches: []
test: ""
asked: "2026-11-10: yes to all (to: Your CLAUDE.md push line is a bare git push, which fails on a brand-new branch. Change it to git push -u origin HEAD. OK?)"
proof: []
unmeasured: "A wording fix the meter has no fixture for, and the user approved it."
---

## Change

- `CLAUDE.md`, `## Safety Rails`: every line that pushes runs `python3 ~/.claude/scripts/tools/pull_keep_index.py <repo>` right before `git -C <repo> push -u origin HEAD`, in place of a bare `git -C <repo> push`.
- `tests/scripts/test_guidance_rules.py`: the push-line test checks the new wording.
- `claude/.claude/scripts/gates/git_discipline_gate.py`: the autostash deny message names `git -C <repo> push -u origin HEAD`.
- `tests/scripts/test_git_discipline_gate.py`: the deny-message assertion checks the new wording.

## Evidence

User rule. A bare push on a new branch with no upstream fails unless `push.autoSetupRemote` is set. `pull_keep_index.py` now skips the pull on such a branch, so the push that follows must set the upstream itself.

## Result

A first push from a handed-over line sets the upstream and succeeds.

## Watch

None: a user rule.

## Back-out

Restore the bare `git -C <repo> push` wording in `CLAUDE.md`, `tests/scripts/test_guidance_rules.py`, the gate's autostash deny message and `tests/scripts/test_git_discipline_gate.py`.
