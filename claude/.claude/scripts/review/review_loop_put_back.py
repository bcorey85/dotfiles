"""review_loop_put_back.py: putting protected lines (sign-off lines, or comment lines no finding names) back in a file
after a coder pass, and the record of each file put back."""
import pathlib
import typing

import protected_lines
import script_utils


class ProtectedPutBack(typing.NamedTuple):
    """One file the loop put protected lines back in (sign-off lines, or comment lines no finding names): their line
    numbers in the text before the pass, and that text and the restored one."""

    path: str
    lost_numbers: list
    before_text: str
    restored_text: str

    @property
    def unchanged(self):
        """True when the put-back left the file as it was before the pass, so no fix to it survives."""
        return self.restored_text == self.before_text


class PassSnapshots(typing.NamedTuple):
    """What the loop records before a coder pass so it can put protected text back after it: the sign-off snapshot,
    the comment snapshot and the criterion-quote snapshot (an AcQuoteSnapshot, never None)."""

    signoffs: typing.Any
    comments: typing.Any
    ac_quotes: typing.Any


def put_back_lines(repo, path, before_text, current, numbers, whole_stretch=True, may_replace=None):
    """Restores the lines `numbers` of `before_text` in `current`, writes the file byte-exact, and returns its
    ProtectedPutBack."""
    restored = protected_lines.restore_protected_lines(before_text, current, numbers, whole_stretch, may_replace)
    script_utils.write_text_atomically(pathlib.Path(repo) / path, restored.encode("utf-8", "surrogateescape"))
    return ProtectedPutBack(path, numbers, before_text, restored)


def fully_put_back_paths(put_back):
    """The paths in `put_back` that went back to their text before the pass."""
    return [entry.path for entry in put_back if entry.unchanged]
