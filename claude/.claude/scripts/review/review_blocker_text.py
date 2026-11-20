"""The text of a blocker line in the review packet: whole when short, its head plus the path of a file holding all of it
when long."""

import hashlib
import pathlib
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import review_fix_state
import script_utils
from review_fix_names import BLOCKER_TEXT_FOLDER

FULL_TEXT_LIMIT = 2000


def full_text_file(text):
    """The file in the review-fix state folder that holds `text`, named by a digest of it so a repeat run writes the
    same file."""
    digest = hashlib.sha256(text.encode()).hexdigest()[:12]
    target = review_fix_state.review_fix_dir() / BLOCKER_TEXT_FOLDER / f"{digest}.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    script_utils.write_text_atomically(target, text + "\n")
    return target


def blocker_text(text):
    """The blocker on one line. Past FULL_TEXT_LIMIT characters: the first FULL_TEXT_LIMIT, then the path of the file
    that holds the whole text."""
    whole = script_utils.one_line(text, None)
    if len(whole) <= FULL_TEXT_LIMIT:
        return whole
    target = full_text_file(text)
    return f"{whole[:FULL_TEXT_LIMIT]} ... [full text: {target}]"
