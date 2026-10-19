---
type: "Change"
title: "The user disabled the Ponytail plugin at user scope with the plugin command"
description: "The user disabled the Ponytail plugin at user scope with the plugin command."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-20T00:00:00-05:00"}
seq: 2
components: ["rule/settings-json"]
evidence: ["removal round", "seeded round", "census", "judgment"]
watches: []
---

## Change

The user disabled the Ponytail plugin at user scope with the plugin command. Its rule text (876 words) no longer reaches the main session or any subagent type. The plugin's own review and audit commands leave with it. The plugin stays installed. No agent file, skill file, or hook script changed. The `PONYTAIL_SUBAGENT_MATCHER` line in the `env` block of the settings is dead text now. The settings gate denies a model write to that file, so the user ran the command by hand.

## Evidence

removal round, seeded round, census, judgment

## Result

Two agent types ran with and without the text. In the coder, the text bought no measured code quality and cost about 14 thousand Sonnet tokens per dispatch. In the backend architect, the text saved tokens and cost plan quality. Plans with the text had about a quarter less Opus output and came about 50 seconds sooner. Those plans listed fewer edge cases and fewer success criteria. Most of them ordered a batch job that reads a stale card position after its first archive, and no plan without the text did. A coder then built the batch job from each plan. Half of the builds from plans with the text left a position gap after a batch archive, against none from plans without it. The type check and the old tests passed in every build, so neither check shows the fault. The coder alone caught the plan fault in a third of the cases. At the architect, the removal costs about 4,900 more Opus output tokens per plan and about 50 seconds. Output quality ranks above tokens, so the removal pays that cost on purpose. Each subagent dispatch and the main session also lose about 1,900 tokens from the first prompt, paid again in each response. The rest is judgment. The specialist reviewers, the plan reviewer, the test writer, the review loop, and the main session never ran with and without the text. In the work logs, the rate of hand-found complaints on coder output did not fall after the plugin went live. A plugin update can change the text with no edit by the user. The plugin's commands had four typed uses in the whole prompt history, so their loss is small. Limits: one ticket, one hidden fault, and few plans and builds behind each number. With one faulty build less, the builds read as no difference. Every seeded reviewer round since the plugin went live ran with the text on, so the drop owed one check, and that check ran on the same day. With no plugin text, the reviewer of fix diffs caught every known regression on the same seeded trees, as each saved run with the text did. It filed no false fix item, and it named more verified defects than the saved run. No token saving showed at that reviewer, because the cost of one review varies more from run to run than the plugin text weighs. The relay sessions of that check, a near-constant workload, each started about 1,800 fresh tokens lighter. Limits of that check: one run per tree, against a saved run from ten hours before, and the saved run also held two more label lines. The batch mode of the escape skill still names the plugin as a trigger word, with no use on record.

## Watch

—

## Back-out

—
