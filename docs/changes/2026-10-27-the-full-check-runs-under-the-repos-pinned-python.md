---
type: "Change"
title: "The full check runs under the repo's pinned Python, and a missing module is an environment gap"
description: "full_check.py puts the pyenv shims first on PATH in a repo with a .python-version file, and a check that fails on a missing third-party module reports an environment gap that never stops the phase."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T23:59:00-05:00"}
seq: 140
kind: "fix"
components: ["script/full-check", "script/review-loop-script", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_full_check_missing_a_third_party_module_converges_with_the_environment_gap"
asked: "2026-10-27: agent-evals-64 assigned queue items code-full-check-runs-make-lint-py-with-an and agent-shells-resolve-python3-to-an-interpreter"
proof: []
unmeasured: ""
---

## Change

- `full_check.pinned_interpreter_env`: in a repo with a `.python-version` file, the check runs with
  `$PYENV_ROOT/shims` (default `~/.pyenv/shims`) first on PATH, when that folder exists.
- `full_check.environment_gap`: a failed check whose log says `No module named X` returns
  `not run (environment gap: No module named 'X')`. This applies only when X's top-level name is not a folder or
  `.py` file at the repo root or under `src/`. That result is not a failure, so the loop sends no repair coder and
  does not stop the phase.
- `review-loop.md` Step 6 and the packet's `full_check` values name the environment gap.

## Evidence

- A /code full check ran `python3 -m <tool>` under the agent shell's system Python, got "No module named X", tried
  one repair and stopped the phase as critical-blocker. The same lint passed under the pinned pyenv interpreter.
- The pyenv-shims, environment-gap and loop-converges tests fail on the old scripts.

## Result

- A pinned repo's check runs under its pinned interpreter. A missing third-party module converges the review with
  the gap named in the hand-back. A missing module of the repo's own code is still a failure.

## Watch

—

## Back-out

Revert the commit.
