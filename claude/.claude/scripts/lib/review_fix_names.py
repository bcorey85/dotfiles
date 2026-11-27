"""The folder, file and state-key names of the review-fix state. No imports: the Write gate loads this module on every
code-fork Write, so it must stay free of anything slow."""

REVIEW_FIX_FOLDER = "review-fix"
STATE_FILE_NAME = "state.json"
ASK_FINDINGS_NAME = "ask-findings.md"
# The folder under the review-fix state folder that holds the whole text of a long blocker line.
BLOCKER_TEXT_FOLDER = "blocker-text"
# The approval-only asks still open, a JSON object {"paths": ..., "wanted": [...]} (the shape is documented at
# `approval_asks_store.read_saved_asks`), which the next review loop run of the repo reloads and rewrites with the asks
# it files again. Each ruling on an approval ask, accepted or rejected, removes its path and its wanted entries. Kept
# beside the state file.
APPROVAL_ASKS_NAME = "approval-asks.json"
HELD_APPROVAL_NAME = "held-approval-changes.json"
# The findings a fix coder was given when it died mid-edit, less those on a reverted approval-only path (an approval
# ask now), with the partial diff: the next review loop run of the repo sends those not on a held file to the coder
# again, and keeps only the held ones after that pass, or when none of its findings is left to send (no diff then); a
# run that stops before the first fix pass leaves the file as it is.
PARTIAL_FIX_NAME = "partial-fix.json"
# The run folder's findings file: `/fix` passes it to `--fix`, and a fork writes it for `launch --also-fix` to add
# findings to the fix run asks-done printed. The run folder is the one place the fork may write.
RUN_FOLDER_FINDINGS_NAME = "fix-findings.md"
# The ask field that holds the epoch time the ask was filed in the saved asks of a review-fix packet.
FILED_AT_KEY = "filed_at"
# The state key that holds the epoch time the packet's held plan impact was filed: a relayed `decide` needs a user
# turn typed after it.
PLAN_IMPACT_FILED_AT_KEY = "plan_impact_filed_at"
# Set by asks-done when it prints a fix run, cleared when that run launches. The fork-write gate reads it.
PENDING_LAUNCH_KEY = "asks_launch_pending"
# Set when a --correct call had a row fail and the stored answers leave no ask to apply (the pending launch was
# dropped), so the retry is allowed with no pending launch.
CORRECT_OPEN_KEY = "correct_open"
# Who ruled on each ask, a list with one entry per ask: set by the asks-done that prints the fix run, then reset to the
# decider of each ask a later `asks-done --correct` re-answers, so a session correction drops that ask's `--user-ruled`.
ASKS_DECIDED_BY_KEY = "asks_decided_by"
# The indexes of the approval asks asks-done put back to their pre-pass text: they hold nothing for the coder, and a
# retry of the call keeps them.
RESTORED_INDEXES_KEY = "restored_approval_indexes"
# The identity keys of a packet's saved state, set when the packet is saved (apart from `packet_id`). A kept packet
# that holds a packet's held asks copies them, as it relaunches the same review run.
PACKET_IDENTITY_KEYS = ("skill", "scope", "lane", "iter", "review_round", "spec_iter", "fix_rounds",
                        "post_cap_passes", "status", "branch", "source", "fixed_paths", "files_touched")
