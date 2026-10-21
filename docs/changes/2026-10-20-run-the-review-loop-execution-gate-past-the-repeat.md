---
type: "Change"
title: "Run the review-loop execution gate past the repeat-check cap"
description: "The review loop's one full quality-check run now carries a trailing `#skip-quality-cap`, so the cap on repeated checks cannot deny the gate that decides convergence."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-20T20:21:22-05:00"}
seq: 12
components: ["agent/review-loop"]
evidence: ["judgment", "census"]
watches: []
---

## Change

`agents/review-loop.md` Step 6: the execution gate command ends with a trailing `#skip-quality-cap` comment. One added sentence says why: this run is the gate, so the cap on repeated checks must not deny it.

## Evidence

The quality-check-cap hook denies a check command when its last run is newer than the last Write or Edit in the session. It keys that state by the hook event's session id, and a subagent shares the session id of its parent. So a loop that runs its gate again with no edit since the last run gets a deny in place of a result. This happens on a second iteration where the coder changed no code, or on a new loop dispatch after an earlier one ran the same command. Step 6 has no exit code to act on, so the loop cannot converge on evidence. A bench fork hit this deny on a repeated test run.

The newest work-log pull counts 228 quality-check-cap blocks in subagent runs. The intake does not split them by agent type, so the share that hit the review loop's gate is not known.

## Result

The line is in place. No run since then. The trade: the gate can now run the full suite one more time when nothing changed since the last run. That costs one suite run of wall-clock and no tokens beyond the call itself.

## Watch

None. `security-hook-block-log.jsonl` holds no quality-check-cap rows. The review-queue hook-block table counts them for all subagents together, and edit_watch.py does not read that table.

## Back-out

Delete the `#skip-quality-cap` clause and the sentence after it from Step 6.
