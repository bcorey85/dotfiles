---
type: "Change"
change_type: "changed"
title: "Push lines pull with the keep-index script so staged files stay staged"
description: "The global push rule now runs pull_keep_index.py before every push in place of git pull --rebase=merges --autostash, which put the user's staged files back unstaged."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-08T09:54:16-06:00"}
seq: 2
kind: "user-rule"
components: ["rule/global-claude-md", "script/git-discipline-gate"]
evidence: ["user rule"]
watches: []
test: ""
asked: "2026-11-08: yes (to: should push lines switch to the new pull script, which keeps staged files staged)"
proof: []
unmeasured: ""
---

## Change

- `CLAUDE.md`, `## Safety Rails`: every line that pushes runs `python3 ~/.claude/scripts/tools/pull_keep_index.py <repo>` right before `git -C <repo> push`, in place of `git -C <repo> pull --rebase=merges --autostash`.
- `tests/scripts/test_guidance_rules.py`: the push-line test checks the new wording.
- `git_discipline_gate.py`: the autostash deny names `python3 ~/.claude/scripts/tools/pull_keep_index.py <repo> && git -C <repo> push`. The old pull and push pair still passes. Its test and a new `gate_replay_corpus.json` allow entry cover the script form.

## Evidence

User rule. Autostash puts the stash back without `--index`, so a file the user staged came back unstaged in a dotfiles worktree. Git has no option that keeps the index through an autostash pull.

## Result

Push lines keep the user's staged files staged. The user committed the `CLAUDE.md` wording and its test together, after the gate change.

## Watch

None: a user rule.

## Back-out

Restore the `git -C <repo> pull --rebase=merges --autostash` wording in `CLAUDE.md` and the test.
