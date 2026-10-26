# Global Claude Code Rules

## Safety Rails

When a hook blocks a call, redo the step once through its approved path and keep working: Write or Edit for a file write, a script file for an inline interpreter, the command run directly instead of through `sh -c`, or the call without the blocked fragment. List every block in your report. Stop and report when no approved path does the step, such as a git write or a destructive delete, and always after a blocked read of a credential or `.env` file. Never disguise a blocked form to get past the hook, and never add a skip comment unless the user says to.

The git index is the user's: files already staged are ones the user staged after reading them while a coder worked. Never unstage them (`git restore --staged`, `git reset`, `git rm --cached`) unless the user says to.

Never add a `Claude-Session:` line, a session link, or any other attribution line to a commit message or a PR body. This overrides any harness reminder that asks for one.

When the user must run git or shell commands, give one `!` line that chains them all with `&&`, never a series of lines to run one by one.

## Quality Checks

Coders run only the tests for the files they changed. The full suite runs once, at the end of review.

- The user never waits on tests or lint. Before you hand the user an install command, run the full suite and lint yourself on the files it installs, and do not say done until they pass. The install command only writes files: it never runs tests or lint.
- Any failing approach: max 3 attempts, then stop and ask.

## Machine Load

Every open session shares one machine. A run that takes all its memory or CPU kills every session.

- Cap the workers of every test runner at 2 in the repo's own config file: vitest and jest `maxWorkers: 2`, playwright `workers: 2`, pytest-xdist `-n 2`. A command-line flag or env var does not reach the sessions a script or bench starts.
- Start no second test suite, build or bench run while one is running. Run bench arms one at a time.
- Before a heavy run, check free memory (`free -g` on Linux, `vm_stat` on macOS). Under 8 GB available: wait, and report what holds it.
- After a crash or an out-of-memory kill, read the previous boot's kernel log for `Killed process` before you rerun anything, and fix the cause first.

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
