#!/usr/bin/env python3
"""Print the last stop of a /code, /review or /fix fork for the main session to say word for word.

    python3 ~/.claude/scripts/code/code_relay.py

Run from the directory the Skill call ran in, after it returns. The fork writes every stop to a stop file in the run
folder (code_wait.phase_dir) before it hands back: /code to stop.md, /review and /fix to review-stop.md. This prints
the newer one between USER TEXT markers. When stop.prev.md (the stop.md that phase_start moved aside) is newer than
both stop files, the run wrote no new stop: it exits 1 and writes nothing, unless that stop is a bounced stop.md stop
not yet relayed (below).
A stop with a `To go on:` line waits on the user: the rule says to make no other tool call. A stop without one is a
finished run: the rule says to go on with the skill that invoked it. The relayed stop's name and mtime go in
<run folder>/relayed, so a second relay of the same stop exits 1 and says to relay the Skill result instead.
A stop that waits on the user, in a tree whose source changed after the session's clean review (and no commit since),
is not relayed: the rule sends the main session back through the `To go on:` line to re-run the review round, and
`relayed` stays unwritten. The stop's stamp goes in <run folder>/bounced, so the same stop, relayed again after the
resume wrote no new stop, relays to the user with a first line in the USER TEXT block that says the tree changed
after the converged review. A bounced stop.md stop that phase_start has since moved to stop.prev.md relays the same
way, from stop.prev.md.
"""

import os
import pathlib
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent),
                str(pathlib.Path(__file__).resolve().parent.parent / "lib"),
                str(pathlib.Path(__file__).resolve().parent.parent / "review")]
import code_wait
import handback
import reviewed_tree
import script_utils
from stop_file_names import PREVIOUS_STOP_FILE, STOP_FILE, STOP_FILES

RELAYED_FILE = "relayed"
BOUNCED_FILE = "bounced"
GO_ON_PREFIX = "To go on:"
RULE = ("Say the text between the markers as your whole reply, word for word. Make no other tool call before the "
        "user's next message: no search, read, edit or check of the fork's work. A fix goes back through "
        "the stop's `To go on:` line.")
FINISHED_RULE = ("Say the text between the markers word for word. The run is finished: when a skill you are running "
                 "invoked this one, go on with that skill's next step; otherwise make no other tool call.")
RE_REVIEW_FEEDBACK = ("Re-run the review round on the current tree: files changed after the review "
                      "converged.")
RE_REVIEW_RULE = ("Do not say the stop. Run the command on the stop's `To go on:` line below with this feedback, "
                  f"then relay again.\nFeedback: {RE_REVIEW_FEEDBACK}\n")
UNREVIEWED_NOTE = "The tree changed after the converged review; this stop is unreviewed."
FALLBACK = "Say the Skill result word for word as your whole reply, and make no other tool call."


def newest_stop(folder):
    """The stop file of the run folder with the newest mtime. Counts the previous-stop file too: when it is the
    newest, the fork wrote no new stop, and an older stop file must not be relayed as new."""
    stops = [folder / name for name in (*STOP_FILES, PREVIOUS_STOP_FILE) if (folder / name).is_file()]
    if not stops:
        return None
    return max(stops, key=lambda stop: stop.stat().st_mtime_ns)


def go_on_line(text):
    """The first `To go on:` line of a stop, or None for a finished run."""
    for line in text.splitlines():
        if line.startswith(GO_ON_PREFIX):
            return line
    return None


def edited_after_clean_review(repo):
    """True when the session's latest hand-back for `repo` is clean, was stored after the HEAD commit, and the work
    tree is not a reviewed one. Fail-open on purpose: no session id, no repo, no commit, no hand-back or a tree that
    cannot be fingerprinted means the stop relays as it always has."""
    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not session:
        return False
    top_path = script_utils.repo_root(repo)
    if top_path is None:
        return False

    top = str(top_path)
    committed_at = script_utils.head_commit_time(top)
    if committed_at is None:
        return False
    # `%ct` is whole seconds and a hand-back's `ts` is a float: a hand-back stored just before the commit has a `ts`
    # above `committed_at`, so a second is added. Failing the other way only means a relay.
    if not handback.clean_handback_since(session, top, committed_at + 1):
        return False
    # record_reviewed records nothing without a fingerprint, so every stop there would read as edited and bounce
    # once before reaching the user.
    tree = reviewed_tree.reviewed_fingerprint(repo)
    if tree is None:
        return False
    return not reviewed_tree.is_reviewed(session, repo, tree)


def is_stamped(stamp_file, stamp):
    return stamp_file.is_file() and stamp_file.read_text().strip() == stamp


def user_text_reply(repo, text, add_unreviewed_note):
    """(0, reply) that relays `text` to the user. The unreviewed note is added only to a stop that waits on the user,
    when `add_unreviewed_note` is set and the tree is still edited after the clean review."""
    waits = go_on_line(text) is not None
    if waits and add_unreviewed_note and edited_after_clean_review(repo):
        text = f"{UNREVIEWED_NOTE}\n\n{text}"
    rule = RULE if waits else FINISHED_RULE
    return 0, f"{rule}\n-----BEGIN USER TEXT-----\n{text}\n-----END USER TEXT-----"


def relay_bounced_stop(repo, folder, previous_stop, stamp):
    """Relay a stop.md stop that was bounced and then moved aside by the resume's phase_start, which wrote no new
    stop. The user still gets the unreviewed note when the tree is still edited."""
    text = previous_stop.read_text().strip()
    script_utils.write_text_atomically(folder / RELAYED_FILE, stamp + "\n")
    return user_text_reply(repo, text, add_unreviewed_note=True)


def relay(repo):
    """(exit code, text) for the newest stop file of the run folder of `repo`."""
    folder = code_wait.phase_dir(repo)
    stop = newest_stop(folder)
    if stop is None:
        return 1, f"code_relay: no stop file in {folder}. {FALLBACK}"
    if stop.name == PREVIOUS_STOP_FILE:
        bounced_stamp = f"{STOP_FILE} {stop.stat().st_mtime_ns}"
        if is_stamped(folder / BOUNCED_FILE, bounced_stamp) and not is_stamped(folder / RELAYED_FILE, bounced_stamp):
            return relay_bounced_stop(repo, folder, stop, bounced_stamp)
        return 1, (f"code_relay: {stop} is the stop phase_start moved aside, so this run wrote no new stop. "
                   f"{FALLBACK}")

    stamp = f"{stop.name} {stop.stat().st_mtime_ns}"
    relayed = folder / RELAYED_FILE
    if is_stamped(relayed, stamp):
        return 1, f"code_relay: {stop} was relayed already, so this run wrote no new stop. {FALLBACK}"

    text = stop.read_text().strip()
    go_on = go_on_line(text)
    waits = go_on is not None
    bounced = folder / BOUNCED_FILE
    already_bounced = is_stamped(bounced, stamp)
    # A stop bounced once relays on the next call: a resume that wrote no new stop would bounce it forever.
    if waits and not already_bounced and edited_after_clean_review(repo):
        script_utils.write_text_atomically(bounced, stamp + "\n")
        return 0, RE_REVIEW_RULE + go_on
    script_utils.write_text_atomically(relayed, stamp + "\n")
    return user_text_reply(repo, text, add_unreviewed_note=already_bounced)


def main(argv):
    if len(argv) != 1:
        sys.exit("usage: python3 ~/.claude/scripts/code/code_relay.py")
    code, text = relay(os.getcwd())
    print(text, file=sys.stdout if code == 0 else sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
