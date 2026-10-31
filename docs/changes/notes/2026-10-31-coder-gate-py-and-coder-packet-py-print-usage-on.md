---
type: "Change"
change_type: "fixed"
title: "coder_gate.py and coder_packet.py print usage on --help and change nothing"
description: "A session that asks coder_gate.py or coder_packet.py for help now gets the usage line and exit 0. Before, `coder_gate.py set --help` stored a gate and `coder_packet.py --help` crashed."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-31T17:52:37-05:00"}
seq: 4
kind: "fix"
components: ["script/code"]
evidence: ["tests"]
watches: []
test: "tests/scripts/test_coder_gate.py::CoderGateEnvironmentTests::test_help_after_any_verb_prints_usage_and_sets_no_gate"
asked: ""
proof: []
unmeasured: ""
---

## Change

`coder_gate.py` checks for a `--help` or `-h` argument before any verb runs, prints its usage line and exits 0, so `set --help` writes no gate file. The check matches whole arguments, so a stored command such as `"python3 -m pytest -h"` is not read as help. `coder_packet.py` runs the same check before it reads its arguments. The check is `script_utils.help_requested`, which `plan_check.py` now uses in place of its own inline copy.

## Evidence

A bench session ran `coder_gate.py set --help`, got a gate in place of help, and had to clear it. `coder_packet.py --help` raised an index error.

## Result

New tests: `test_coder_gate.py::CoderGateEnvironmentTests::test_help_after_any_verb_prints_usage_and_sets_no_gate` (no gate file after `set --help`, `set -h`, `set <cmd> --help`, `--help`, `summary -h`) and `test_coder_packet.py::CoderPacketTest::test_help_prints_usage_and_exits_0`. Both test files pass (85 tests); lint is clean.

## Watch

None: a usage fix with no intake number.

## Back-out

Revert the commit.
