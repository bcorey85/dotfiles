"""path_summary.py: shortens a long list of file paths by folding the files of a directory into one entry."""
import collections
import posixpath


def directory_key(path, depth):
    """The directory of `path` cut to its first `depth` folders; "" for a file at the top."""
    directory = posixpath.dirname(path)
    folders = directory.split("/") if directory else []
    return "/".join(folders[:depth])


def folded_entries(paths, depth, never_fold=()):
    """One entry per directory key at `depth`: the file's own path when it is alone there, else `dir/ (N files)`.
    A directory that holds a path of `never_fold` lists each of its files. Entries come in the order their
    directory first appears."""
    groups = collections.defaultdict(list)
    for path in paths:
        groups[directory_key(path, depth)].append(path)
    protected = {directory_key(path, depth) for path in never_fold}

    entries = []
    for directory, members in groups.items():
        if len(members) == 1 or directory in protected:
            entries.extend(members)
        elif directory:
            entries.append(f"{directory}/ ({len(members)} files)")
        else:
            entries.append(f"top-level files ({len(members)} files)")
    return entries


def protected_first(entries, depth, never_fold):
    """`entries` with those in a directory of `never_fold` (at `depth`) ahead of the others, each group in its
    own order. A folded entry names a directory that is not protected, so it stays behind."""
    protected = {directory_key(path, depth) for path in never_fold}
    ahead = [entry for entry in entries if directory_key(entry, depth) in protected]
    behind = [entry for entry in entries if directory_key(entry, depth) not in protected]
    return [*ahead, *behind]


def collapse_paths(paths, max_entries, never_fold=()):
    """The paths as they are when there are at most `max_entries`. Otherwise one entry per directory, taken at the
    deepest directory depth that gives at most `max_entries` entries; a directory that holds a path of
    `never_fold` keeps its files listed one by one. When no depth gives at most `max_entries`, the first
    `max_entries` entries of the depth with the fewest entries, those of `never_fold` directories ahead of the
    others, and an `and N more` entry."""
    paths = list(paths)
    if len(paths) <= max_entries:
        return paths

    deepest = max(len(posixpath.dirname(path).split("/")) for path in paths)
    fewest = None
    for depth in range(deepest, 0, -1):
        entries = folded_entries(paths, depth, never_fold)
        if len(entries) <= max_entries:
            return entries
        if fewest is None or len(entries) < len(fewest[0]):
            fewest = (entries, depth)
    fewest_entries, fewest_depth = fewest
    ordered = protected_first(fewest_entries, fewest_depth, never_fold)
    hidden = len(ordered) - max_entries
    return [*ordered[:max_entries], f"and {hidden} more"]
