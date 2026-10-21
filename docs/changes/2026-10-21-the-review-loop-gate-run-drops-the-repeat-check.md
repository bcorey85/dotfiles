---
type: "Change"
title: "The review-loop gate run drops the repeat-check skip marker"
description: "The review loop's Step 6 gate run no longer ends with a skip marker for the repeat-check cap. The auto-mode classifier denied every command that carried the marker, so the gate run never ran. This reverses the 2026-10-20 change."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T07:58:25-05:00"}
seq: 5
components: ["agent/review-loop"]
evidence: ["work incident"]
watches: []
---

## Change

- `agents/review-loop.md`, Step 6: the gate run command no longer carries a trailing `#skip-quality-cap` comment, and the sentence that told the loop to add it is gone.
- The quality-check-cap hook will exempt the review loop's gate run in code: a review-loop agent with a command that writes `/tmp/review-gate.log`. That hook change ships in the next script install.

## Evidence

Work incident: the auto-mode classifier reads a trailing skip comment as an attempt to get past a hook. It denied the loop's gate run in every phase of one /code run. The same deny hit the log-review-metrics call that followed. So the marker blocked the check it was meant to let through.

## Result

Edited 2026-10-21. Until the hook exemption installs, a gate run that repeats an earlier full run with no edit between them can still get the repeat-check deny. That case costs one rerun after the next edit, not a skipped gate.

The exemption installed 2026-10-21. The second script fix batch replaces it with a per-agent run record, so the loop's gate run is its own first run.

## Watch

None. The intake counts hook blocks by rule in `review-queue.txt`, but classifier denials are not hook blocks and no intake script counts them.

## Back-out

Restore the clause that adds the trailing `#skip-quality-cap` comment to the Step 6 gate run.
