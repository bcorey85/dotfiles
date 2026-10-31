---
type: "Change"
change_type: "changed"
title: "The read ban of the test writer now says that a hook refuses the read"
description: "The read ban of the test writer now says that a hook refuses the read, names the shell and search commands as the same read, and keeps declaration lines open by either route."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-20T00:00:00-05:00"}
seq: 5
kind: "behavior"
components: ["agent/test-writer"]
evidence: ["census"]
watches: []
---

## Change

The read ban of the test writer now says that a hook refuses the read, names the shell and search commands as the same read, and keeps declaration lines open by either route. The opencode copy gets the same text without the hook sentence, because no read hook runs there.

## Evidence

census

## Result

The read hook binds the read tool alone. The shell is the first route of the writer, not its fallback. Half of the 140 logged dispatches were rig stand-ins that give a fixed reply in place of the writer. In 34 of the 69 bench dispatches of the real writer, the writer printed function bodies of the code under test through the shell. Over the whole store, the hook never fired in 19 of the 35 dispatches with such a print. After a denied read, about a third of the attempts moved to the shell. A symbol lookup came before most of them, and every such lookup returned no answer, because no language server was registered for the bench language. A line-by-line read of those shell re-takes found declaration lines only in 14 of 20, and the ban leaves those open. One re-take printed more than two body lines. The writer tried the lookup only after a denied read, so a working lookup cannot reach the prints that follow no denial. Three earlier statements in this row were wrong. The first called those lookups working. It came from a matcher that trusted the error flag, and the no-server reply carries none. The second said that nine in ten of the re-takes printed function bodies, and its matcher is not on file. The third gave the rate as 35 of 140. That count pooled the real writer with the stand-ins, which never act, so it halved the rate. So the data does not clear the lookup tool: the route that the agent file and the hook both name was dead in every run that tried it. The data also does not name the lookup as the fix. All but one of the 140 dispatches were bench runs. Effect unmeasured: an earlier census showed that words alone did not hold this rule, and the hook still leaves the shell route open. The live check is the count of shell commands in test-writer transcripts that name a non-test source path, split by whether the output holds a function body. Its baseline is 34 of 69 bench dispatches of the real writer with a function body printed. The newest bench runs of the writer gave 8 of 16. No live baseline exists, because the one live dispatch wrote no test file. No outcome on file shows a cost of those prints. Writers that printed bodies killed the same share of planted defects as writers that did not. The code under test there is correct, so a test that pins a bug cannot show.

## Watch

—

## Back-out

—
