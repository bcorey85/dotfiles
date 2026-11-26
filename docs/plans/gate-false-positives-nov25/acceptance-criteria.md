# Acceptance Criteria — gate-false-positives-nov25

## Ticket item 1

- **AC1** — The gate treats a promised follow-up as started when the same turn launched background agents (Agent calls with run_in_background) that the follow-up waits on, and a regression case covers it.
- **AC2** — A first-person step that is not a report on the background work ("I'll push them") still blocks after a background launch, and a report step with no launch in the turn still blocks.

## Ticket item 2

- **AC3** — The gate skips text inside a fenced or delimited draft block (or a message the turn labels as a draft for the user), and a test covers a drafted reply with first-person promises passing.
- **AC4** — A first-person promise outside the draft block in the same message still blocks.

## Ticket item 3

- **AC5** — A test in the gate's suite asks "Shall I add a Jira link from A to B?" and "Want me to label the ticket?" and both pass as outward asks; the current local-step cases still block. Fails before the change.

## Ticket item 4

- **AC6** — A gate test feeds a Bash call with rg and no path and gets back an allow decision with updatedInput holding the command with the dot path appended; a no-path rg reading from a pipe stays allowed unchanged. Fails before the change.
- **AC7** — A no-path rg inside a compound command (more than one step) is still denied with the fixed command, so an allow never covers a step the permission flow has not seen.
- **AC8** — The change file for item 4 holds the hook's median run time before and after, next to a bare Python start.

## Ticket item 5

- **AC9** — The gate's refusal names the base to review from (the last reviewed commit), or `/review` with no base falls back to the commits the gate counts as unreviewed.

## Ticket item 6

- **AC10** — The hook's message names a cap command that works on the host OS (or names run_in_background alone on darwin).

## Ticket item 7

- **AC12** — A test in tests/scripts/ passes the reply "It checks the skill list against what is staged." and a reply that names another worktree's staged files by its path, and still blocks "I staged the change." with an empty index. It fails before the fix and passes after.

## Ticket item 8

- **AC13** — A test shows the gate lets a push through when the last review is logged, its only open findings are plan-file text, and the commits since then touch only the plan directory. The same test shows the gate still blocks a push after a code commit.

## Ticket item 9

- **AC14** — effective_status reads a valid full-check receipt, a test gives it such a packet and gets deferred, and bash tests/run.sh passes.

## Branch

- **AC11** — `bash tests/run.sh` passes.
