---
type: "Change"
change_type: "fixed"
title: "code-step stops when it cannot read a phase's checks"
description: "code-step marked a phase done after running none of its Automated Verification checks when it could not read them as commands. It did not know `cargo`, so every Rust phase skipped its tests. It now reads more command forms and stops when an item stays unreadable. The same batch fixes how it joins coder reports, revives a stopped coder and writes the commit prefix."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T08:30:23-05:00"}
seq: 11
kind: "fix"
components: ["script/code-step", "script/plan-format"]
evidence: ["work incident", "tests"]
watches: []
---

## Change

- **Automated Verification:** the command reader accepts `cargo`, `./` and `sh ` with the other tool names. If an item stays unreadable, the phase stops and is not marked done. The stop names `tick N` for a check that cannot be automated, to use only on the user's word. An item that says N/A or none counts as no check.
- **Added coder:** when the plan gains lines during a run and a second coder is dispatched, its report joins the first coder's report. The reviewer gets the reasons for both, and the commit subject comes from the first coder.
- **Stopped coder:** only the hand-back from the coder that stopped revives the run. The stop text says to resume that coder with SendMessage, then run `after-coder`.
- **Commit prefix:** the suggested commit starts with the ticket key from the plan folder or branch. A key needs an uppercase project key (`LED-7`, `ABC-123`), so `node-20` or `oauth-2` gets no prefix.
- Other fixes from the same pass: the closing-phase baseline, a deeper heading that ended a phase section, and the PLAN-IMPACT reader.

## Evidence

Work incident: in one work slice, after-review printed "0 command(s) green (none)" for a phase that listed two `cargo test` commands, and then marked the phase done. A probe of that plan showed that the old reader read both items as non-commands and the new reader reads both. A hand re-check of that ticket found no failure that the skipped checks hid. A code review of the staged script found five defects, and all five were fixed before install.

## Result

Installed 2026-10-21. 256 unit tests pass. The state-machine walk explored 564,470 paths with 0 failures.

## Watch

None. No intake metric counts phases marked done without a verification run.

## Back-out

Restore the previous `code-step.py`, `plan_format.py` and `test_code_step.py` from the dotfiles history.
