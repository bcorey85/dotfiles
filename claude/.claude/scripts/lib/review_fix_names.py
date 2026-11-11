"""The folder, file and state-key names of the review-fix state. No imports: the Write gate loads this module on every
code-fork Write in a run folder, so it must stay free of anything slow."""

REVIEW_FIX_FOLDER = "review-fix"
STATE_FILE_NAME = "state.json"
ASK_FINDINGS_NAME = "ask-findings.md"
# Set by asks-done when it prints a fix run, cleared when that run launches. The fork-write gate reads it.
PENDING_LAUNCH_KEY = "asks_launch_pending"
