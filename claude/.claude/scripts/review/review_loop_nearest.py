"""The nearest-other-functions block of the review loop's smell-reviewer prompt: for each function the change under
review adds, the repo functions whose token shape is close. It reads the shape pass of /refactor branch-prep, so a
helper that redoes an existing one under another name and shape reaches the reviewer as a named candidate."""
import pathlib
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
REFACTOR_SCRIPTS = SCRIPT_DIR.parents[1] / "skills" / "refactor" / "scripts"
sys.path[:0] = [str(SCRIPT_DIR.parent / "lib"), str(REFACTOR_SCRIPTS)]
import refactor_flow
import script_utils
import shape_clones
import source_text


def skipped_note(reason):
    return f"Nearest other functions: not read ({reason})."


def partial_note(reason):
    return f"Nearest other functions: partly read ({reason})."


def nearest_functions_text(repo, base, owned):
    """The prompt block that lists the nearest other functions of each function the owned files add to the work tree
    against `base` (HEAD when empty). "" when no added function has a neighbour; one note line for each part of the
    shape pass that could not run."""
    diff_text = script_utils.git_output(repo, *source_text.DIFF_FLAGS, "-U0", base or "HEAD")
    if diff_text is None:
        return skipped_note("git could not diff the tree")
    try:
        diff_files = source_text.parse_unified_diff(diff_text)
    except ValueError as error:
        return skipped_note(f"cannot parse the diff: {error}")
    try:
        untracked = refactor_flow.untracked_files(repo)
    except refactor_flow.RefactorFlowError as error:
        return skipped_note(str(error))

    # Neighbours come from the whole repo; only the added functions are limited to the files this reviewer owns.
    owned_paths = set(owned)
    owned_diff_files = [diff_file for diff_file in diff_files if diff_file.path in owned_paths]
    owned_untracked = [file for file in untracked if file.path in owned_paths]
    result = shape_clones.branch_shapes(owned_diff_files, owned_untracked, repo)
    lines = shape_clones.catalog_lines(result)
    # With the repo unread nothing was read, so the note says "not read", not "partly read".
    note_for = skipped_note if result.repo_unread else partial_note
    lines.extend(note_for(note) for note in result.notes)
    return "\n".join(lines)
