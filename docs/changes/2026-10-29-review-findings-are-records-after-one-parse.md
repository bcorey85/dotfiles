---
type: "Change"
change_type: "changed"
title: "Review findings are records after one parse"
description: "Review-loop findings are parsed once into Finding records, and a merged finding keeps its parts as a list instead of text joined with ' Also reported: ', so each part keeps its own path and line."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T10:38:49-05:00"}
seq: 255
kind: "fix"
components: ["script/review-loop-script", "script/full-check-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_merged_finding_keeps_each_part_with_its_own_line"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New `review/finding_record.py`: a frozen `Finding` (text, path, line, finding_class, title, identifiers, parts),
  `parse_finding()` as the one parse, `combine()` for a merged finding and `each_part()` to walk its parts.
  The merged text is still the parts joined with `MERGED_SEPARATOR` (' Also reported: '), so output is unchanged.
- `review_loop_findings.py`, `review_loop_script.py`, `review_loop_packet.py` and `full_check_gate.py` pass records.
  The per-site regex helpers (`finding_file`, `finding_class`, `finding_title`, `identifiers`) are gone, and no code
  splits text on ' Also reported: '.
- `tests/run.sh` adds `finding_record.py` to the review-flow complexity lint.

## Evidence

- Findings were bare strings re-parsed by regex at about ten sites, and a merged finding was split back on its
  separator, so a later part could be read at the first part's path.

## Result

- The named test pins that a three-part merge keeps each part at its own path and line, keeps its parts flat and
  prints the same joined text. Existing expected output is unchanged.
- The review-loop gate's `count_findings` stays as it was: it only counts entries, and records added nothing there.

## Watch

—

## Back-out

Revert the commit.
