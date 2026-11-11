#!/usr/bin/env python3
"""Print the last stop of a /code, /review or /fix fork for the main session to say word for word.

    python3 ~/.claude/scripts/code/code_relay.py

Run from the directory the Skill call ran in, after it returns. The fork writes every stop to a stop file in the run
folder (code_wait.phase_dir) before it hands back: /code to stop.md, /review and /fix to review-stop.md. This prints
the newer one between USER TEXT markers. A stop with a `To go on:` line waits on the user: the rule says to make no
other tool call. A stop without one is a finished run: the rule says to go on with the skill that invoked it. The
relayed stop's name and mtime go in <run folder>/relayed, so a second relay of the same stop, or a run that wrote no
new stop, exits 1 and says to relay the Skill result instead.
"""

import os
import pathlib
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent),
                str(pathlib.Path(__file__).resolve().parent.parent / "lib")]
import code_wait
import script_utils
from stop_file_names import STOP_FILES

RELAYED_FILE = "relayed"
GO_ON_PREFIX = "To go on:"
RULE = ("Say the text between the markers as your whole reply, word for word. Make no other tool call before the "
        "user's next message: no search, read, edit or check of the fork's work. A fix goes back through "
        "the stop's `To go on:` line.")
FINISHED_RULE = ("Say the text between the markers word for word. The run is finished: when a skill you are running "
                 "invoked this one, go on with that skill's next step; otherwise make no other tool call.")
FALLBACK = "Say the Skill result word for word as your whole reply, and make no other tool call."


def newest_stop(folder):
    stops = [folder / name for name in STOP_FILES if (folder / name).is_file()]
    if not stops:
        return None
    return max(stops, key=lambda stop: stop.stat().st_mtime_ns)


def waits_on_user(text):
    return any(line.startswith(GO_ON_PREFIX) for line in text.splitlines())


def relay(repo):
    """(exit code, text) for the newest stop file of the run folder of `repo`."""
    folder = code_wait.phase_dir(repo)
    stop = newest_stop(folder)
    if stop is None:
        return 1, f"code_relay: no stop file in {folder}. {FALLBACK}"

    stamp = f"{stop.name} {stop.stat().st_mtime_ns}"
    relayed = folder / RELAYED_FILE
    if relayed.is_file() and relayed.read_text().strip() == stamp:
        return 1, f"code_relay: {stop} was relayed already, so this run wrote no new stop. {FALLBACK}"

    text = stop.read_text().strip()
    script_utils.write_text_atomically(relayed, stamp + "\n")
    rule = RULE if waits_on_user(text) else FINISHED_RULE
    return 0, f"{rule}\n-----BEGIN USER TEXT-----\n{text}\n-----END USER TEXT-----"


def main(argv):
    if len(argv) != 1:
        sys.exit("usage: python3 ~/.claude/scripts/code/code_relay.py")
    code, text = relay(os.getcwd())
    print(text, file=sys.stdout if code == 0 else sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
