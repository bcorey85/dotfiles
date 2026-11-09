# The /review and /fix fork run

**The run folder.** `git rev-parse --path-format=absolute --git-path code-phase`, run in your starting directory, prints it; `<run folder>` below means that path. Create it with `mkdir -p` before the first write. You write only `<run folder>/review-handoff.txt`, `<run folder>/fix-findings.md` and `<run folder>/review-stop.md`, each with a Bash heredoc. A coder makes every other edit.

**Launch.** Run the skill's launch line with `--detach`, in the foreground. Then run the `code_wait.py review --loop <loop dir>` command it prints, again while it prints `Still working`. On exit 1 of this call or of any later `code_wait.py review` call, do the step its last line names.

**Reviewers.** On `ACTION: dispatch-reviewer`: in one message, dispatch one `Agent` per listed line, `subagent_type` its agent, `model` only when the line names one, prompt `Read <prompt file> whole and do that task.` Then run `python3 ~/.claude/scripts/code/code_wait.py review --loop <loop dir> <agentId> <report file> ...`, one pair per agent, each id and path written out as its own word (no shell variable, loop or function), again while it prints `Still working`; it writes each report as its agent finishes. Handle its output the same way. When it says the loop finished, run the packet command it printed.

**The packet's ACTION lines.** Do what they say, with these readings:

- An instruction to present something and wait for the user, for direction or for a reply, or to end the turn, is a STOP.
- A launch line the packet prints runs with `--detach`, in the foreground, then waits as above.
- On `show-plan-impacts` or `redispatch`: dispatch one `coder` to add the printed deviation lines under `## Plan Deviations` in the plan, then run `python3 ~/.claude/scripts/code/code_wait.py agent <agentId>`, again while it prints `Still working`.
- An ask you may decide yourself: decide it and run asks-done with `--by session`.

**Ending the run hands back.** Write the final text to `<run folder>/review-stop.md`, then make it your final reply. It holds the packet's USER TEXT block word for word, every line an ACTION says to present (each ask with its question and proposed change, each plan-impact question, each blocker), and your closing line. A STOP ends with the line `To go on: /<skill> resume <your feedback>`; a run that waits on nobody has no such line. A stop never ends on a question. Never call AskUserQuestion. Never end the run while an agent you dispatched works.

**Resume.** When the task text starts with `resume`, the rest is the user's reply to `<run folder>/review-stop.md`. Launch nothing new unless the reply asks for the stop's next run. Answer that stop: for asks, run `python3 ~/.claude/scripts/review/review_fix.py asks-done --by user <outcome>...` with one outcome per ask in the stop's order; for a plan-impact ruling, run `python3 ~/.claude/scripts/review/review_fix.py decide discuss` and then the decide command it prints, `--by user`. Then do what that output's ACTION lines say.
