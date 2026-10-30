---
type: "Change"
change_type: "changed"
title: "/review launches the scripted review loop"
description: "A working-tree /review now runs the scripted review loop that cut median review tokens 42% on the bench (1,295,705 → 751,367); the packet, gate-mark and asks handling are unchanged, and the agent stays for handoff blocks, base=, file scope, +fast/+deep, iter= and /fix."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T08:29:54-05:00"}
seq: 339
kind: "structured"
components: ["skill/review", "script/review-fix", "script/review-loop-script", "script/code-step", "script/handback"]
evidence: ["replacement bench", "tests"]
watches: ["review-scripted-loop-cache-read", "scripted-review-loop-escapes"]
test: "tests/scripts/test_review_fix_script.py"
asked: ""
proof: ["2026-10-26-scripted-review-loop-with-bounded-re-review-vs", "2026-10-26-scripted-review-loop-vs-review-loop-agent-16-runs"]
impact: {"metric": "tokens", "before": 1295705, "after": 751367, "unit": "tokens", "finding": "2026-10-26-scripted-review-loop-with-bounded-re-review-vs"}
unmeasured: ""
overlap: "The /code switch to the scripted loop also watches escapes per code-reviewer run, so that reading covers both callers, and its `scripted-review-loop-escapes` window starts 2026-10-27 (the /code switch), so the reading cannot isolate /review; the cache-read watch filters on the review caller and reads /review alone."
---

## Change

`/review` with no `handoff:` block, no `base=`, no file path, no `+fast` / `+deep` and no `iter=` runs `review_fix.py launch` as a background Bash call. The verb records the dispatch store row that the Agent hook writes for a review-loop, writes the prompt file, and runs `review_loop_script.py` in the foreground, so the Bash completion notice wakes the session. `review_fix.py packet --skill review` then reads the hand-back the script stored, and the gate mark and asks-done steps run unchanged. The prompt-file and command helpers moved into `review_loop_script.py`, so /code and /review build the launch the same way.

The review-loop agent stays for the cases the script does not cover:

- A `handoff:` block: the script does not honor its exact `files:` scope or its prior issues.
- `base=` branch-exit reviews and file-scoped reviews: the script scopes the working tree against HEAD only.
- `+fast` / `+deep` and `iter=`: the script reads no modifier or counter.
- A re-dispatch after a plan-impact ruling: the script reads no ruling lines.
- `/fix`: its `fix-first` mode is not scripted, so `/fix` keeps the agent.

## Evidence

The bounded re-review bench ran the scripted loop against the review-loop agent, 12 runs per arm (the registered 16 was cut to 12 by user ruling), on a review-first diff. The script cut median tokens 42% (1,295,705 → 751,367) and wall-clock 45%, and fixed a median 10 seeded defects to the agent's 9. The 16-run bench before it found both gaps inside run-to-run spread. Neither bench ran through `/review`'s own start, so `/review`'s gain is read by the cache-read watch. At work, `/code`'s switch about halved review-loop cache read per `/code` run, on one script day against two agent days (disposition HOLD; finding 2026-10-28-scripted-review-loop-at-work-first-two-days-cache, from `review-loop-cost-rows.jsonl`).

## Result

`tests/scripts/test_review_fix_script.py` and `test_code_step_review_script.py` pass; the full suite passed in the review's full check.

## Watch

- `review-scripted-loop-cache-read`: review-loop cache-read tokens per `/review` loop run (caller `review`), down.
- `scripted-review-loop-escapes`: review escapes per code-reviewer run, flat.

## Back-out

Delete the Script branch of step 1 in `skills/review/SKILL.md`, the script mention in its `stop-no-handback` bullet, and "the loop script stores it itself" in step 2. The `launch` verb then goes unused; its leftover "run `launch` again when the script started it" hint in `review_fix.py` is harmless.
