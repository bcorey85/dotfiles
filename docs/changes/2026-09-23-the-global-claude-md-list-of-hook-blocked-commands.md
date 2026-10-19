---
type: "Change"
title: "The global CLAUDE.md list of hook-blocked commands now names the forms the model kept trying"
description: "The global CLAUDE.md list of hook-blocked commands now names the forms the model kept trying: credential reads of `.env*` and `*.key` files, including through `cat`, inline interpreters with the instruction to write a script file, `sh -c` and `bash -c`, `rm -rf`, `xargs`, and `find -exec`."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-23T00:00:00-05:00"}
seq: 6
components: ["rule/global-claude-md"]
evidence: ["hook block log"]
watches: ["hook-block-list-in-claude-md"]
---

## Change

The global CLAUDE.md list of hook-blocked commands now names the forms the model kept trying: credential reads of `.env*` and `*.key` files, including through `cat`, inline interpreters with the instruction to write a script file, `sh -c` and `bash -c`, `rm -rf`, `xargs`, and `find -exec`.

## Evidence

hook block log

## Result

Over three days of work logs, the safety gates blocked 183 commands, rising from 31 to 81 a day. Inline interpreters, indirect shells, `.env` and key-file reads, forced recursive deletes and `xargs` made 154 of them. The line named credential reads only in general terms, and the other four kinds not at all. Each block wastes a response at about 111k of Opus cache read in the main session. The added words cost about 40 tokens on every load. Effect unmeasured. Live check: blocks per day in the block log for those rule names, before and after.

## Watch

—

## Back-out

restore the prior list.
