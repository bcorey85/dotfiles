"""The resume record of a /code run and the check that a resume which changed source got a review.

phase_start.py --resume writes <run folder>/resume.json: {"repo", "head", "tree", "at", "denied"}. The code-fork's Write
of stop.md asks resume_deny_reason first (gates/fork_write_scope.py): a resume whose tree moved with no review loop
started in the run is denied once.

A missing resume.json means the run is not a resume, so the check passes (fail-open). So does a run folder that holds
a loop-dir file, whatever resume.json holds. An unreadable resume.json or a failed fingerprint raises; the gate that
calls this denies the Write, naming the review to run (fail-closed), on every try until the review loop starts. A
failed git call in the path list gives a wrong list (changed paths missing, or declared notes paths left in), not a
raise.
"""
import json
import pathlib
import sys
import time

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(SCRIPTS_DIR / folder) for folder in ("lib", "code")]

import notes_paths
import reviewed_tree
import script_utils
import stop_file_names


class ResumeRecordError(ValueError):
    """A resume.json that is not an object with the five keys."""


RESUME_FILE = "resume.json"
RESUME_KEYS = ("repo", "head", "tree", "at", "denied")
SHOWN_PATHS = 5
DENY_TEXT = ("fork-write-scope: this /code resume changed source since phase_start.py --resume ({count} path(s): "
             "{shown}), and no review loop ran on it. Run step 5 (code_review_start.py ... --base <phase base>, "
             "the sha phase_start.py printed) before the stop; write the stop again only when the run ends before "
             "review.")


def write_resume(run_folder, record):
    script_utils.write_text_atomically(pathlib.Path(run_folder) / RESUME_FILE, json.dumps(record, indent=2) + "\n")


def record_resume(run_folder, repo):
    """Write the resume record: the repo's HEAD and its reviewed tree against that HEAD, now. Raises when the repo has
    no HEAD or cannot be fingerprinted."""
    head = script_utils.head_commit(repo)
    if head is None:
        raise script_utils.GitCallError(f"resume_review_gate: {repo} has no HEAD commit, so the resume has no base")

    fingerprint = reviewed_tree.reviewed_fingerprint(repo, base=head)
    if fingerprint is None:
        raise script_utils.GitCallError(
            f"resume_review_gate: could not fingerprint the tree of {repo} against {head}")

    top, tree_hash = fingerprint
    write_resume(run_folder, {"repo": top, "head": head, "tree": tree_hash, "at": time.time(), "denied": False})


def clear_resume(run_folder):
    """Remove the resume record, so a plain phase start is not a resume."""
    (pathlib.Path(run_folder) / RESUME_FILE).unlink(missing_ok=True)


def read_resume(resume_file):
    """The parsed record. Raises ResumeRecordError for text that is not an object with the five keys."""
    try:
        record = json.loads(resume_file.read_text())
    except json.JSONDecodeError as error:
        raise ResumeRecordError(f"{resume_file}: not JSON: {error}") from error
    if not isinstance(record, dict):
        raise ResumeRecordError(f"{resume_file}: top level is not an object")

    missing = [key for key in RESUME_KEYS if key not in record]
    if missing:
        raise ResumeRecordError(f"{resume_file}: missing {missing}; expected keys {list(RESUME_KEYS)}")
    return record


def changed_source_paths(repo, head):
    """The paths changed against `head` that are not notes paths."""
    entries, errors = notes_paths.committed_notes_list(repo)
    for error in errors:
        print("[resume-review-gate] " + error, file=sys.stderr)
    changed = script_utils.changed_files(repo, head, with_deleted=True)
    return [path for path in changed if not notes_paths.is_notes_path(path, entries)]


def resume_deny_reason(stop_path):
    """The deny text for a stop.md Write in a resume run whose source moved with no review loop, else None. The deny is
    given once: the record then holds `denied`."""
    run_folder = pathlib.Path(stop_path).parent
    resume_file = run_folder / RESUME_FILE
    if not resume_file.is_file():
        return None

    # A started review loop passes before the record is read, so a corrupt record cannot block a run that reviewed.
    if (run_folder / stop_file_names.LOOP_DIR_FILE).exists():
        return None

    record = read_resume(resume_file)
    if record["denied"]:
        return None

    fingerprint = reviewed_tree.reviewed_fingerprint(record["repo"], base=record["head"])
    if fingerprint is None:
        raise script_utils.GitCallError(f"resume_review_gate: could not fingerprint the tree of {record['repo']} "
                                        f"against {record['head']}")
    if fingerprint[1] == record["tree"]:
        return None

    write_resume(run_folder, {**record, "denied": True})
    paths = changed_source_paths(record["repo"], record["head"])
    return DENY_TEXT.format(count=len(paths), shown=", ".join(paths[:SHOWN_PATHS]))
