"""The `files:` entries of a review handoff block, built from a list of paths. Any handoff, any module: the caller
supplies the paths (from git) and the per-path text it already holds."""


def file_entry_lines(paths, change_by_path, default_change, extra_lines_by_path=None):
    """The `    - path:` / `      change:` lines for each path, in order. A path found in change_by_path keeps that
    text; any other path gets default_change. extra_lines_by_path adds already formatted lines under a path's entry."""
    extra_lines_by_path = extra_lines_by_path or {}
    lines = []
    for path in paths:
        lines += [f"    - path: {path}", f"      change: {change_by_path.get(path) or default_change}",
                  *extra_lines_by_path.get(path, [])]
    return lines
