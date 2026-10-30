"""capped_review.py: the one owner of `effective_status`, the status every reader decides clean on.
It imports nothing from handback.py, which imports it."""

import pathlib
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import reviewed_tree
from script_utils import is_blocker

# The status for a loop that stopped at its round budget with findings left open.
CAP_REACHED = "cap-reached"
DEFERRED = "deferred"


def effective_status(packet, repo):
    """A `cap-reached` packet reads as `deferred` when it holds no blocker (no `blockers` entry, no blocker in
    findings_remaining), no open class and no scoped reviewer that could not run, its full check passed, and that
    check's tree fingerprint (`full_check_tree`) equals the fingerprint of the work tree at `repo` now. A check older
    than the last change, one with no fingerprint, or a repo that cannot be fingerprinted keeps `cap-reached`. Any
    other status is returned as it is."""
    import full_check

    if packet["status"] != CAP_REACHED:
        return packet["status"]
    if packet["blockers"] or any(is_blocker(item) for item in packet["findings_remaining"]):
        return CAP_REACHED
    if packet["open_classes"] or packet["unrun_reviewer"]:
        return CAP_REACHED
    if packet["full_check"] != full_check.PASSED or not packet["full_check_tree"] or not repo:
        return CAP_REACHED

    found = reviewed_tree.fingerprint(repo)
    if found is None or found[1] != packet["full_check_tree"]:
        return CAP_REACHED
    return DEFERRED
