---
type: "Change"
change_type: "fixed"
title: "pull_keep_index names the session that wrote the dirty files"
description: "A pull before push that refuses in a shared checkout names a session as holder of the dirty files only when its transcript records a write to one; otherwise it says the owner is unknown and lists the candidates."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T22:18:04-06:00"}
seq: 3
kind: "fix"
components: ["script/pull-keep-index", "script/session-registry"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_pull_keep_index.py::PullKeepIndexTest::test_the_session_that_wrote_the_dirty_file_is_named_and_the_other_is_not"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

The shared route's two refusals (diverged branch, overwrite) named the first live session whose registry `cwd` sat in
the repo, so a pusher could message a session that never touched the dirty files. The refusal now reads every live
session in the repo (`session_registry.other_live_sessions_in`) and each one's transcript plus its subagents'
transcripts (`session_registry.session_and_subagent_transcripts`, on top of `session_transcript`). It names a session only when
exactly one has an Edit, Write, MultiEdit or NotebookEdit call with an absolute path on a dirty path, recorded after
the HEAD commit time, every other transcript was read, and the pushing session wrote none of them. Otherwise it says
the owner is unknown and lists the live sessions as candidates, with unread transcripts named apart.
The route choice is unchanged. `epoch_of_timestamp` moves from `human_turn_lookup` to `script_utils`, so the coder
gate, which loads `loop_transcript`, does not load `human_turn_lookup` and its imports.

## Evidence

On 2026-11-25 a bench-base push was told agent-evals-7c held three dirty files that it never edited.

## Result

New tests: two sessions in one checkout where one wrote the dirty file name that one and never the other; no writer,
two writers or an unread transcript give an unknown owner. Full suite 6677 tests, 0 failed.

## Watch

A writer whose cwd is outside the repo is not searched, so its files read as owner unknown. A wrong name is still
possible when the real writer changed the file through Bash after another session's logged write since HEAD.

## Back-out

Revert the commit.
