---
type: "Change"
change_type: "removed"
title: "The global CLAUDE.md lost its pointer to the orchestration file and its Ansible Vault rule"
description: "The global CLAUDE.md lost its pointer to the orchestration file and its Ansible Vault rule."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-27T00:00:00-05:00"}
seq: 10
kind: "behavior"
components: ["rule/global-claude-md", "rule/orchestration"]
evidence: ["removal round", "judgment"]
watches: []
---

## Change

The global CLAUDE.md lost its pointer to the orchestration file and its Ansible Vault rule. The naming rule stays.

## Evidence

removal round, judgment

## Result

Run as the coder, with and without the text. Without the naming rule, the coder wrote no abbreviated or single-letter names, the same as with it, but that was one run on a fixture in the rule's own example domain, and the user added the rule on purpose, so it stays by judgment. Subagents never receive the orchestration file, and the main session gets it injected anyway, so the pointer told no agent anything it could act on. The user chose to drop the vault rule: without it, the coder put a new API key into the repo in plain text, with a warning and a vault command to fix it. With it, the coder referenced a vault variable and kept the key out of the repo. The removal is a quality trade the user accepted. The two blocks are about 50 words, about 115 tokens on every main-session and subagent request. One run per task.

## Watch

—

## Back-out

restore the blocks from git.
