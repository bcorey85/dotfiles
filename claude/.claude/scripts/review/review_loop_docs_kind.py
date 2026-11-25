"""The review loop's `docs_kind` label, set by script on a docs-class finding: `new` when the cited line is one the
diff under review added, `stale` when the line was there before it. Round one reads the change under review; a later
round reads the fix diff the round before it wrote. A finding the script cannot place gets no label, and neither
does a finding of a resumed loop's first round, which comes after round one and has no fix diff."""

import pathlib
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import change_added_ranges as change_added_ranges_lib
import diff_ranges
import script_utils
from handback import DOCS_CLASS
from review_loop_held import held_path_in_repo

STALE = "stale"
NEW = "new"
DOCS_KINDS = (STALE, NEW)


def change_added_ranges(repo, base=""):
    """{path: [(first, last)]} of the lines the working tree adds against `base` (HEAD when empty), renames followed
    and every untracked file counted whole. None when git cannot answer, as in a repo with no commit."""
    return change_added_ranges_lib.change_added_ranges(repo, base, detect_renames=True)


def docs_kind(repo, added, finding):
    """The label of one finding record against `added`, the {path: ranges} of the diff its round read. "" (no label)
    when the round has no diff (`added` is None), the class is not docs, or the finding names no line of a text file
    the tree holds under that path from the repo root, or under that absolute path inside the repo."""
    if added is None or finding.finding_class != DOCS_CLASS:
        return ""
    if not finding.path or finding.line <= 0:
        return ""
    # A reviewer may cite the file by absolute path; the diff names it from the repo root.
    cited_path = held_path_in_repo(finding.path, repo)
    if pathlib.PurePath(cited_path).is_absolute():
        return ""
    cited_file = pathlib.Path(repo) / cited_path
    cited_lines = script_utils.read_text_lines(cited_file)
    if cited_lines is None or len(cited_lines) < finding.line:
        return ""

    path_ranges = added.get(cited_path, [])
    on_added_line = diff_ranges.in_ranges(path_ranges, finding.line, slack=0)
    return NEW if on_added_line else STALE
