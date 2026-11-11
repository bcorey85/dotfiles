# Acceptance criteria

- **AC1** — A review loop that converges leaves no lint violation that the repo's configured ruff, oxlint or eslint reports on any changed file, test files included; one it cannot repair stops the loop as critical-blocker with the linter output.
- **AC2** — A repo with no configured linter, or a linter missing from PATH, gets no lint stop.
- **AC3** — A hunk whose only change is whitespace, line breaks, quote style or a trailing comma before a closing bracket adds no lines to the change under review, so reverting it never counts as removed work.
- **AC4** — A hunk with a real change still counts its added lines, and the guard still stops a fix pass that removes half or more of a change of 10 or more lines.
- **AC5** — The scoped test and full-check runs carry the env assignments listed for the repo in `~/.claude/gate-env.json`; a plan's assignment for the same name wins; a malformed file fails loudly naming the file.
- **AC6** — `bash tests/run.sh` passes from the checkout.
- **AC7** — A /code stop that follows a converged review, in a tree whose source changed after that review, goes back to the review round before the main session relays it; a second relay of the same stop with no new stop written shows the stop with a line that says the tree changed after the converged review; an edit only to plan or notes files, or a commit made since the review, relays as before.
