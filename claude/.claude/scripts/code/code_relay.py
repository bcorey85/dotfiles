#!/usr/bin/env python3
"""Print the /code fork's last stop for the main session to say word for word.

    python3 ~/.claude/scripts/code/code_relay.py

Run from the repo root after the /code Skill call returns. The fork writes every stop to <run folder>/stop.md
(code_wait.phase_dir) before it hands back; this prints that text between USER TEXT markers, under the rule that the
main session says it as its whole reply and makes no other tool call. It notes the stop file's mtime in
<run folder>/relayed, so a second relay of the same stop, or a run that wrote no new stop, exits 1 and says to relay
the Skill result instead.
"""

import os
import pathlib
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent),
                str(pathlib.Path(__file__).resolve().parent.parent / "lib")]
import code_wait
import script_utils

STOP_FILE = "stop.md"
RELAYED_FILE = "relayed"
RULE = ("Say the text between the markers as your whole reply, word for word. Make no other tool call before the "
        "user's next message: no search, read, edit or check of the fork's work. A fix goes back through "
        "the stop's `To go on:` line.")
FALLBACK = "Say the /code Skill result word for word as your whole reply, and make no other tool call."


def relay(repo):
    """(exit code, text) for the stop file of the run folder of `repo`."""
    folder = code_wait.phase_dir(repo)
    stop = folder / STOP_FILE
    if not stop.is_file():
        return 1, f"code_relay: no stop file at {stop}. {FALLBACK}"

    stamp = str(stop.stat().st_mtime_ns)
    relayed = folder / RELAYED_FILE
    if relayed.is_file() and relayed.read_text().strip() == stamp:
        return 1, f"code_relay: {stop} was relayed already, so this run wrote no new stop. {FALLBACK}"

    text = stop.read_text().strip()
    script_utils.write_text_atomically(relayed, stamp + "\n")
    return 0, f"{RULE}\n-----BEGIN USER TEXT-----\n{text}\n-----END USER TEXT-----"


def main(argv):
    if len(argv) != 1:
        sys.exit("usage: python3 ~/.claude/scripts/code/code_relay.py")
    code, text = relay(os.getcwd())
    print(text, file=sys.stdout if code == 0 else sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
