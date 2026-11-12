# Review loop batch 2: no stale launch inputs, whole carried findings, leave-it outcome, split-commit credit

No Jira ticket. The source is six agent-evals queue items; their Done-when text follows verbatim.

Source: ~/agent-evals/queue/review-fork-reads-a-stale-review-handoff-file-and.md (all six items are session-written)

## Acceptance

1. review-resume-launches-the-fix-loop-after-a-failed: The resume step launches the loop only after the findings file holds the new findings, by checking its content or by a script that writes and launches in one step.
2. review-resume-launches-the-fix-loop-after-a-failed: The resume step has a way to stop a loop it launched by mistake.
3. review-fork-reads-a-stale-review-handoff-file-and: The handoff file is cleared or rewritten before any loop launch, or the loop refuses a handoff older than the fork's start.
4. review-fork-reads-a-stale-review-handoff-file-and: A fork that relaunches a loop stops the earlier loop first.
5. review-fork-reads-a-stale-review-handoff-file-and: A test pins both.
6. fix-skill-re-runs-stale-findings-after-a-failed: The fix skill refuses to launch the loop unless the findings file was written in this run (fresh mtime or a run id inside it).
7. fix-skill-re-runs-stale-findings-after-a-failed: Stopping a /fix run clears or archives its findings file.
8. asks-done-logs-accepted-for-a-leave-it-option: An ask answered with a no-change option logs an outcome that says no change was made (rejected, or a named outcome) and prints no fix launch line.
9. asks-done-logs-accepted-for-a-leave-it-option: A second asks-done call on a logged ask either corrects it or fails naming the logged outcome.
10. decide-adopt-handoff-cuts-carried-findings-mid: The adopt handoff carries every finding in full, and a test feeds it a long finding and asserts the whole text reaches the reviewer prompt.
11. decide-adopt-handoff-cuts-carried-findings-mid: The Plan Deviations line `decide adopt` prints is written to the plan it names, or the command stops and says it did not write it.
12. split-commit-loses-review-credit-for-the-rest: A second commit whose resulting tree (HEAD after commit plus remaining work tree) matches the reviewed fingerprint earns credit.
13. split-commit-loses-review-credit-for-the-rest: A real edit after the first commit still needs a review.
