---
type: "Change"
change_type: "fixed"
title: "The inline interpreter hint docstring says the gate blocks stdin code"
description: "The inline-interpreter hint's docstring said the Bash gate does not block code fed on stdin to a bare interpreter; the gate does block it, and the docstring now says so."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T12:06:58-06:00"}
seq: 18
kind: "user-rule"
components: ["script/inline-interpreter-hint"]
evidence: ["judgment", "user rule"]
watches: []
test: ""
asked: "2026-11-22: asked by the user"
proof: []
unmeasured: ""
---

## Change

`scripts/gates/inline_interpreter_hint.py` module docstring: "which the gate does not block" → "which the gate also
blocks". No code changed.

## Evidence

`bash-safety-gate.sh` has an `interpreter_stdin` block for `python3 -`, heredocs and pipes into a bare interpreter.

## Result

Docstring only; behavior unchanged.

## Watch

None.

## Back-out

Revert the line.
