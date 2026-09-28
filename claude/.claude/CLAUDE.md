# Global Claude Code Rules

## Safety Rails

Hooks block: `rm` with `-r` or `-f`, inline interpreters (`python3 -c`, `node -e`: write a script file and run it), `sh -c` and `bash -c`, reads of `.env*` and `*.key` files, sudo, SSH/scp/rsync, `xargs`, `find -exec`, pipe-to-shell, force-push, commit or push on main, `git stash`, `git commit --amend`, destructive resets, shell writes to tracked files, and coder writes to test files. When a hook blocks you, report the block and stop. Never rephrase the command to get past it, and never add a skip comment unless the user says to.

## Quality Checks

Coders run only the tests for the files they changed. The full suite runs once, at the end of review.

- Any failing approach: max 3 attempts, then stop and ask.

## Compact instructions

When you compact, keep decisions with their reasons, every measured number, open items in order, commit hashes, file paths, and the rules that bind the next step. Drop tool output and narrative.

## Engineering Judgment

- **Name for the domain, not the data shape.** Take names from the ticket and the code's own domain terms. Never name a value for its container or role alone (`rows`, `data`, `input`, `result`, `items`); say what it holds (`timekeepers`, `newTimekeeper`). Keep every qualifier the domain needs: `compareDateRangeErrors`, not `compareErrors`. Single letters only for loop indexes.
