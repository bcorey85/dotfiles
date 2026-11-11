"""The folder, file and state-key names of the review-fix state. No imports: the Write gate loads this module on every
code-fork Write in a run folder, so it must stay free of anything slow."""

REVIEW_FIX_FOLDER = "review-fix"
STATE_FILE_NAME = "state.json"
ASK_FINDINGS_NAME = "ask-findings.md"
# Set by asks-done when it prints a fix run, cleared when that run launches. The fork-write gate reads it.
PENDING_LAUNCH_KEY = "asks_launch_pending"
# Set when a --correct call had a row fail and the stored answers leave no ask to apply (the pending launch was
# dropped), so the retry is allowed with no pending launch.
CORRECT_OPEN_KEY = "correct_open"
# Who ruled on each ask, a list with one entry per ask: set by the asks-done that prints the fix run, then reset to the
# decider of each ask a later `asks-done --correct` re-answers, so a session correction drops that ask's `--user-ruled`.
ASKS_DECIDED_BY_KEY = "asks_decided_by"
