---
type: "Change"
change_type: "fixed"
title: "rg path gate rewrites a one-step no-path rg through updatedInput"
description: "A one-step, plain rg call with no path now runs with the dot path appended, so the session no longer re-sends the fixed command the gate printed."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T17:10:20-06:00"}
seq: 6
kind: "fix"
components: ["script/rg-path-gate"]
evidence: ["queue: rg-path-gate-rewrites-a-no-path-rg-instead-of"]
watches: []
test: "tests/scripts/test_rg_path_gate.py::RgPathGateTest::test_a_one_step_call_with_no_path_is_allowed_with_the_dot_path_appended"
asked: ""
proof: []
unmeasured: "Each hit cost one denied call and one re-sent call; no logged rate."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

- `gates/rg_path_gate.py`: when the whole command is one plain `rg` call with no path, the gate returns `allow` with `updatedInput.command` set to the command plus ` .`.
- The deny with the fixed command stays for a call that `.` appended would fix, in these forms:
  - a compound command;
  - any output redirection (`>`, `>>`, `2>`, `2>&1`);
  - a comment or subshell around the call (`rg foo # note`, `(rg foo)`);
  - a first word that is not plain `rg`;
  - a `$` or backtick outside single quotes that no backslash escapes, a word starting with `~`, or a glob, brace list or `=command` word, including in words glued to quotes.
- For a one-step command, the printed fix is the raw command text plus ` .`, so its quoting and expansions keep their meaning (`rg "$X"` gives `rg "$X" .`). A compound command keeps the re-quoted fix.
- A call that would still hang with `.` appended is denied with no fixed command, in any of the forms above: a dangling option (`rg foo -g`, `rg -e`), or no pattern (`rg`, `rg -i`).
- `lib/shell_expansion.py` gains `has_substitution_or_tilde`, built on the new `literal_positions` in `lib/shell_quoting.py`.
- `decision()` works out once whether the raw command plus ` .` is a valid fix, and both the allow and the deny read that one value.
- The gate is fail-open. A crash is reported on stderr with the gate name.

## Evidence

The main session ran rg with no path twice in one session. Each time it was denied and re-sent the printed fix.

## Result

Hook wall time, median of 30 runs on a no-path `rg foo` call, next to a bare `python3 -c pass` start:

| | rg gate | bare Python start | gate minus start |
|---|---|---|---|
| Before | 28.5 ms | 8.8 ms | 19.7 ms |
| After | 43.5–44.6 ms (three runs) | 15.2–16.6 ms | about 28 ms |

The bare start was slower in the after runs, so the machine was busier then. The extra shell parsing adds about 8 ms per rg call. The new tests fail before the change and pass after.

## Watch

None.

## Back-out

Revert the commit.
