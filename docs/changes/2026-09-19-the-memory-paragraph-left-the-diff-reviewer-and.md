---
type: "Change"
change_type: "changed"
title: "The memory paragraph left the diff reviewer and the shared calibration file (150 words in each"
description: "The memory paragraph left the diff reviewer and the shared calibration file (150 words in each, 523 remain in the diff reviewer)."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-19T00:00:00-05:00"}
seq: 1
kind: "behavior"
components: ["agent/code-reviewer", "agent/review-loop"]
evidence: ["census", "judgment"]
watches: []
---

## Change

The memory paragraph left the diff reviewer and the shared calibration file (150 words in each, 523 remain in the diff reviewer). The first-action line of the four specialist reviewers no longer names that section, the calibration file now counts four named headings, and the opencode ports lost the name and their skip sentence. The `memory: project` frontmatter line also left the ten reviewer agents and the review loop.

## Evidence

census, judgment

## Result

Auto memory is off in the settings, so the harness gives the reviewers no memory directory and the frontmatter line had no effect. The paragraph still acted. In a census of reviewer transcripts, about seven diff reviewer runs in ten spent about two calls on a hunt for a memory file at guessed paths. About one hunt in five gave notes back, from one global file outside of any repo, and those notes came from other repos or from a different run on the same tree. A few read-only diff reviewers appended to that file by a shell redirect. The runs were unattended, so no human confirmed the lines that tell a reviewer not to flag a thing again. The specialists rarely hunted. The gain is quality first: no reviewer reads a suppression that a different repo wrote, and no read-only reviewer writes notes. The token gain is about two calls in most diff reviews, and 150 always-loaded words in each diff review and in each calibration read. No review finding was traced to the notes, so the size of the quality gain is not measured. The frontmatter line left on judgment, with no measurement behind it. With auto memory on, that line gives these read-only agents the write tools and a memory prompt.

## Watch

—

## Back-out

—
