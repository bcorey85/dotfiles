"""The one reader of `git diff --raw -z` output, as bytes or text. Imports nothing of the toolkit."""

import typing

SUBMODULE_MODE = "160000"
RENAME_OR_COPY = "RC"


class RawDiffError(ValueError):
    """An entry the `git diff --raw -z` format does not allow."""


class RawEntry(typing.NamedTuple):
    """One entry: the modes, object ids and status as text; `paths` in the type of the input, the new path last."""

    old_mode: str
    new_mode: str
    old_sha: str
    new_sha: str
    status: str
    paths: tuple

    @property
    def path(self):
        """The path the entry ends at: the new path of a rename or copy."""
        return self.paths[-1]


def raw_entries(raw):
    """The RawEntry list of `git diff --raw -z` output `raw` (bytes or str). With -z each entry is a
    ":<old mode> <new mode> <old sha> <new sha> <status>" field, then its path, and a second path (the new one) for a
    rename or copy. Raises RawDiffError on an entry the format does not allow."""
    separator = b"\0" if isinstance(raw, bytes) else "\0"
    fields = [field for field in raw.split(separator) if field]
    entries = []
    index = 0
    while index < len(fields):
        meta = fields[index]
        if isinstance(meta, bytes):
            meta = meta.decode()
        meta_fields = meta.lstrip(":").split()
        if len(meta_fields) != 5:
            raise RawDiffError(
                f"git raw diff: expected ':<old mode> <new mode> <old sha> <new sha> <status>', got {meta!r}"
            )
        old_mode, new_mode, old_sha, new_sha, status = meta_fields
        path_count = 2 if status[0] in RENAME_OR_COPY else 1
        paths = tuple(fields[index + 1:index + 1 + path_count])
        if len(paths) != path_count:
            raise RawDiffError(f"git raw diff: entry {meta!r} is missing its path")
        entries.append(RawEntry(old_mode, new_mode, old_sha, new_sha, status, paths))
        index += path_count + 1
    return entries
