# Global Claude Code Rules

## Safety Rails

Hooks block: `rm` with `-r` or `-f`, inline interpreters (`python3 -c`, `node -e`: write a script file and run it), `sh -c` and `bash -c`, reads of `.env*` and `*.key` files, sudo, SSH/scp/rsync, `xargs`, `find -exec`, pipe-to-shell, force-push, commit or push on main, `git stash`, `git commit --amend`, destructive resets, and shell writes to tracked files. After a block, redo the step once through its approved path and keep working: Write or Edit for a file write, a script file for an inline interpreter, the command run directly instead of through `sh -c`, or the call without the blocked fragment. List every block in your report. Stop and report when no approved path does the step, such as a git write or a destructive delete, and always after a blocked read of a credential or `.env` file. Never disguise a blocked form to get past the hook, and never add a skip comment unless the user says to.

The git index is the user's: files already staged are ones the user staged after reading them while a coder worked. Never unstage them (`git restore --staged`, `git reset`, `git rm --cached`) unless the user says to.

## Quality Checks

Coders run only the tests for the files they changed. The full suite runs once, at the end of review.

- Any failing approach: max 3 attempts, then stop and ask.

## Messages to Other Sessions

Keep a `SendMessage` to a peer Claude session under 150 words. Messages to and from your own subagents are exempt. Include the verdict, the numbers the receiver acts on, and what it must do next. If the detail already lives in a file, send the path, not the content. Do not make a file only to hold a message.

## Compact instructions

When you compact, keep decisions with their reasons, every measured number, open items in order, commit hashes, file paths, and the rules that bind the next step. Drop tool output and narrative.

## Engineering Judgment

- **Name for the domain, not the data shape.** Take names from the ticket and the code's own domain terms. Never name a value for its container or role alone (`rows`, `data`, `input`, `result`, `items`); say what it holds (`timekeepers`, `newTimekeeper`). Keep every qualifier the domain needs: `compareDateRangeErrors`, not `compareErrors`. Single letters only for loop indexes.
