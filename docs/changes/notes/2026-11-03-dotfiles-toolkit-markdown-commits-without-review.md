---
type: "Change"
change_type: "fixed"
title: "Dotfiles toolkit markdown commits without review"
description: "The dotfiles repo lists its toolkit Markdown (agents, skills, rules, CLAUDE.md files, orchestration.md) in .claude/notes-paths, so a dirty session commits a Markdown-only rule change without /review."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-03T19:23:17-06:00"}
seq: 7
kind: "fix"
components: ["script/review-commit-gate"]
evidence: ["work incident"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::NotesOnlyCommitTest::test_the_dotfiles_list_passes_a_markdown_only_rule_commit_and_denies_a_skill_script"
asked: ""
proof: []
unmeasured: ""
---

## Change

New `.claude/notes-paths` lists `claude/.claude/agents/`, `claude/.claude/skills/`, `claude/.claude/rules/`, `claude/.claude/CLAUDE.md`, `claude/.claude/orchestration.md`, `claude/.claude/scripts/CLAUDE.md`, `.claude/rules/` and `CLAUDE.md`. Only `.md` files match, so a skill script stays gated. The gate reads the list from HEAD, so it takes effect once the list is on the branch. The cross-repo half of the bug (coder work elsewhere counting here) is fixed by the change "A coder that edited no work tree leaves every repo clean".

## Evidence

A Markdown-only rule commit in dotfiles was denied in a session whose coder work lay elsewhere.

## Result

The new test fails without the list (no file to read) and passes with it. It also shows a `.py` under a listed folder is still denied. `review_commit_gate.py check .claude/notes-paths` exits 0. The gate code is unchanged, so its time is unchanged.

## Watch

None.

## Back-out

Delete `.claude/notes-paths`.
