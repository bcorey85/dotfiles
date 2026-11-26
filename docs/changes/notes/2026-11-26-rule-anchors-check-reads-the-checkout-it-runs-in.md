---
type: "Change"
change_type: "fixed"
title: "rule-anchors check reads the checkout it runs in"
description: "`rule-anchors.sh check` run inside a linked dotfiles worktree now reads that worktree's prompt files and docs/rule-anchors.md, so a stale row there is reported."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T00:53:07-06:00"}
seq: 1
kind: "fix"
components: ["script/rule-anchors"]
evidence: ["tests/scripts/test_rule_anchors.py"]
watches: []
test: "tests/scripts/test_rule_anchors.py::RuleAnchorsTest.test_check_reads_the_checkout_it_runs_in_not_the_one_the_script_lives_in"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`rule-anchors.sh` finds its `.claude` folder from its own symlinked location, the main checkout. When the cwd is inside a dotfiles checkout (its `git rev-parse --show-toplevel` holds `claude/.claude/scripts/tools/rule-anchors.sh`), the script now uses that checkout's `claude/.claude` and `docs/rule-anchors.md`. `RULE_ANCHORS` still overrides only the sidecar path; the prompt files are read from the cwd's checkout when it is a dotfiles checkout. The behavior outside a git repo or in a repo that is not a dotfiles checkout is unchanged. `claude-doctor` runs the check from its own tree, so the doctor keeps reading one tree.

## Evidence

The new test copies the script outside any dotfiles tree, builds a git repo shaped like dotfiles with a stale row, and runs `check` inside it. Before the change it printed `no sidecar at ...` and no STALE line; after, it prints `STALE` and exits 1.

## Result

`check` run in a worktree reports that worktree's drift.

## Watch

—

## Back-out

Remove the `cwd_toplevel` block in `claude/.claude/scripts/tools/rule-anchors.sh` and the new test.
