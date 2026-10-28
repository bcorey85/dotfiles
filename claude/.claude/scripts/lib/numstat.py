"""Added-line counts from `git diff --numstat` output, grouped by any key of the file path."""


def added_lines_by_group(numstat_text, group_of, is_skipped=None):
    """{group: added lines} from `git diff --numstat --no-renames` text. `group_of(path)` names a file's group; a file
    for which `is_skipped(path)` is true, and a binary file (git prints "-"), count nowhere."""
    totals = {}
    for row in numstat_text.splitlines():
        parts = row.split("\t")
        if len(parts) != 3 or not parts[0].isdigit():
            continue

        path = parts[2]
        if is_skipped is not None and is_skipped(path):
            continue

        group = group_of(path)
        totals[group] = totals.get(group, 0) + int(parts[0])
    return totals
