"""Added-line and deleted-line counts from `git diff --numstat -z` output."""


def changed_lines_by_path(numstat_text):
    """{path: (added, deleted)} from `git diff --numstat -z` text: a row is `added\\tdeleted\\tpath\\0`, and a rename
    or copy row is `added\\tdeleted\\t\\0old\\0new\\0`. A renamed file is listed under its new path with only its
    edited lines. A binary file (git prints "-") is left out."""
    counts = {}
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

        if added.isdigit() and deleted.isdigit() and path:
            counts[path] = (int(added), int(deleted))
    return counts


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
