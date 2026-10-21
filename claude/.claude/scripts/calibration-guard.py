#!/usr/bin/env python3
"""SessionStart hook: report an unrestored calibration or mutation seed.

/calibrate and mutation-tester share one lock,
${XDG_STATE_HOME:-$HOME/.local/state}/claude-calibration/lock.json; the old ~/.claude/calibration-lock.json
is read as a fallback (fields file, backup_path, class, ts, kind). The lock is deleted only after the restore is verified, so a lock
that survives into a new session means the restore never happened. This hook prints the paths needed to fix it.
No lock: no output. Always exits 0.
"""
import os
import sys

import hook_input
from hook_input import parse_documents_partial, raw_text


def lock_field(text, key, default, fallback):
    """`jq -r '.key // default' lock 2>/dev/null || echo fallback`, as a shell variable holds it.
    text is None when the lock could not be read: jq fails and the fallback is all there is."""
    if text is None:
        return fallback
    documents, broken = parse_documents_partial(text)
    pieces = []
    failed = broken
    for document in documents:
        if document is None:
            value = None
        elif isinstance(document, dict):
            value = document.get(key)
        else:
            failed = True
            break
        if value is None or value is False:
            value = default
        pieces.append(raw_text(value))
    if failed:
        pieces.append(fallback)
    return "\n".join(pieces).rstrip("\n")


def main():
    home = os.environ.get("HOME", "")
    state_home = os.environ.get("XDG_STATE_HOME") or os.path.join(home, ".local", "state")
    lock = os.path.join(state_home, "claude-calibration", "lock.json")
    if not os.path.isfile(lock):
        # A lock left by a run from before the lock moved out of ~/.claude still has to be reported.
        lock = os.path.join(home, ".claude", "calibration-lock.json")
    if not os.path.isfile(lock):
        return 0
    try:
        with open(lock, "rb") as handle:
            text = handle.read().decode("utf-8", "replace")
    except OSError:
        text = None

    file = lock_field(text, "file", "?", "?")
    backup = lock_field(text, "backup_path", "?", "?")
    seed_class = lock_field(text, "class", "?", "?")
    stamp = lock_field(text, "ts", "?", "?")
    kind = lock_field(text, "kind", "calibrate", "calibrate")

    if kind == "mutation-test":
        what = "MUTATION SEED — a previous mutation-tester run did not finish."
    else:
        what = "CALIBRATION SEED — a previous /calibrate run did not finish."

    message = (
        "⚠️  UNRESTORED %(what)s\n"
        "\n"
        "A deliberate '%(class)s' mutation was applied at %(ts)s and may still be in:\n"
        "  %(file)s\n"
        "\n"
        "Restore it from the backup before doing ANY other work in that repo:\n"
        "  cp \"%(backup)s\" \"%(file)s\"\n"
        "\n"
        "Then verify the file is back to what you expect and remove the lock:\n"
        "  rm \"%(lock)s\"\n"
        "\n"
        "Do not commit until this is resolved. Do not run /calibrate or dispatch\n"
        "mutation-tester until this lock is gone — both refuse to seed on top of an\n"
        "unrestored seed.\n"
    ) % {"what": what, "class": seed_class, "ts": stamp, "file": file, "backup": backup, "lock": lock}
    sys.stdout.buffer.write(message.encode("utf-8", "replace"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
