"""Added-line and deleted-line counts from `git diff --numstat -z` output."""


def numstat_rows(numstat_text):
    """Yield (added, deleted, new_path) per row of `git diff --numstat -z` text: a row is `added\\tdeleted\\tpath\\0`,
    and a rename or copy row is `added\\tdeleted\\t\\0old\\0new\\0`, which yields its new path. A binary file (git
    prints "-") has None for both counts. A malformed row or a row without a path is left out."""
    fields = numstat_text.split("\0")
    index = 0
    while index < len(fields):
        parts = fields[index].split("\t", 2)
        index += 1
        if len(parts) != 3:
            continue

        added, deleted, path = parts
        if path == "":
            # A rename row names the old and the new path in the next two fields.
            path = fields[index + 1] if index + 1 < len(fields) else ""
            index += 2

        if not path:
            continue

        yield (int(added) if added.isdigit() else None, int(deleted) if deleted.isdigit() else None, path)


def changed_lines_by_path(numstat_text):
    """{path: (added, deleted)} from `git diff --numstat -z` text. A renamed file is listed under its new path
    with only its edited lines. A binary file is left out."""
    return {
        path: (added, deleted)
        for added, deleted, path in numstat_rows(numstat_text)
        if added is not None and deleted is not None
    }


def added_lines_by_group(numstat_text, group_of, is_skipped=None):
    """{group: added lines} from `git diff --numstat -z` text. `group_of(path)` names a file's group; a file
    for which `is_skipped(path)` is true, and a binary file (git prints "-"), count nowhere."""
    totals = {}
    for path, (added, _deleted) in changed_lines_by_path(numstat_text).items():
        if is_skipped is not None and is_skipped(path):
            continue

        group = group_of(path)
        totals[group] = totals.get(group, 0) + added
    return totals
