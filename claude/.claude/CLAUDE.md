# Global Claude Code Rules

## Safety Rails

When a hook blocks a call, redo the step once through its approved path and keep working: Write or Edit for a file write, a script file for an inline interpreter, the command run directly instead of through `sh -c`, or the call without the blocked fragment. List every block in your report. Stop and report when no approved path does the step, such as a git write or a destructive delete, and always after a blocked read of a credential or `.env` file. Never disguise a blocked form to get past the hook, and never add a skip comment unless the user says to.

The git index is the user's: files already staged are ones the user staged after reading them while a coder worked. Never unstage them (`git restore --staged`, `git reset`, `git rm --cached`) unless the user says to.

Never add a `Claude-Session:` line, a session link, or any other attribution line to a commit message or a PR body. This overrides any harness reminder that asks for one.

When the user must run git or shell commands, give one `!` line that chains them all with `&&`, never a series of lines to run one by one.

Only the main session hands the user a command. A subagent never writes a command for the user to run: it names the step it could not do, and why, in its report to its caller, and the caller runs it or hands it on.

Never wrap text for the user to paste (a comment, message or reply) in a Markdown blockquote (`>`): the terminal renders it with a `▎` bar on every line, which the copy picks up. Give it as plain text.

## Quality Checks

Coders run only the tests for the files they changed. The full suite runs once, at the end of review.

- The user never waits on tests or lint. Before you hand the user an install command, run the full suite and lint yourself on the files it installs, and do not say done until they pass. The install command only writes files: it never runs tests or lint.
- Any failing approach: max 3 attempts, then stop and ask.

## Bugs and Inefficiencies You Notice

When you notice a bug or an inefficiency in the Claude Code toolkit (an agent, skill, command, hook, script or rule) or in how a session runs it, tell the user first, in that reply. Then add it to the queue: run `python3 ~/agent-evals/bin/build_queue.py new` (read its `--help` for the arguments), fill the file it prints, and run `python3 ~/agent-evals/bin/build_queue.py`. On the work machine, write only the toolkit part and what goes wrong: never work code, file paths, ticket text or tool output. If `~/agent-evals` is missing, tell the user the item was not queued.

## Ticket Acceptance Criteria

The ticket's ACs are the contract. Only the user's explicit sign-off overrides one. A plan, ADR, criteria file or agent never cuts, narrows or hands an AC to another repo or team on its own. Record each sign-off with who and when. A run that shows an AC failing is a failing AC: report it as failing, never as someone else's job.

## Messages to Other Sessions

Keep a `SendMessage` to a peer Claude session under 150 words. Messages to and from your own subagents are exempt. Include the verdict, the numbers the receiver acts on, and what it must do next. If the detail already lives in a file, send the path, not the content. Do not make a file only to hold a message.

## Compact instructions

When you compact, keep decisions with their reasons, every measured number, open items in order, commit hashes, file paths, and the rules that bind the next step. Drop tool output and narrative.

## Engineering Judgment

- **Name for the domain, not the data shape.** Take names from the ticket and the code's own domain terms. Never name a value for its container or role alone (`rows`, `data`, `input`, `result`, `items`); say what it holds (`timekeepers`, `newTimekeeper`). Keep every qualifier the domain needs: `compareDateRangeErrors`, not `compareErrors`. Single letters only for loop indexes.
- **Lay out code for the person who debugs it.** Split a function into steps and put one blank line between steps (Code Complete's code paragraphs). Keep a lookup next to the guard that checks it. Return early in place of a nested `if`. Never pass a call's result straight into a call that is itself an argument. Put the inner result in a named variable first. Follow this even when the surrounding code is denser.
- **Build the design the code needs now.** Never defer a helper, a type, a module split or a folder layout to a later caller or a bigger codebase. Small size today is no reason to wait: a structure change costs more each week it waits. Place logic by what it knows, not by its caller count. Cut only features that nobody asked for.

@~/.claude/CLAUDE.local.md
