"""The folder, file and state-key names of the review-fix state. No imports: the Write gate loads this module on every
code-fork Write, so it must stay free of anything slow."""

REVIEW_FIX_FOLDER = "review-fix"
STATE_FILE_NAME = "state.json"
ASK_FINDINGS_NAME = "ask-findings.md"
# The paths of the approval-only files with an open user-only ask, a JSON object of each path to the blob id its edit
# is measured against, which the next review loop run of the repo reloads and rewrites with the paths it files again,
# and each ruling on a user-only ask, accepted or rejected, removes its path. Kept beside the state file.
APPROVAL_ASKS_NAME = "approval-asks.json"
# The run folder's findings file: `/fix` passes it to `--fix`, and a fork writes it for `launch --also-fix` to add
# findings to the fix run asks-done printed. The run folder is the one place the fork may write.
RUN_FOLDER_FINDINGS_NAME = "fix-findings.md"
# Set by asks-done when it prints a fix run, cleared when that run launches. The fork-write gate reads it.
PENDING_LAUNCH_KEY = "asks_launch_pending"
# Set when a --correct call had a row fail and the stored answers leave no ask to apply (the pending launch was
# dropped), so the retry is allowed with no pending launch.
CORRECT_OPEN_KEY = "correct_open"
# Who ruled on each ask, a list with one entry per ask: set by the asks-done that prints the fix run, then reset to the
# decider of each ask a later `asks-done --correct` re-answers, so a session correction drops that ask's `--user-ruled`.
ASKS_DECIDED_BY_KEY = "asks_decided_by"
