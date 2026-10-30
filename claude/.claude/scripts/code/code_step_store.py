"""code_step_store.py: where a /code run's state lives: state.json in the repo's code-step folder, the archive an abort
leaves, the session's list of repos, and the transaction that holds one verb's state changes until it ends.

Installed beside code_step.py and imported by code_step_core, whose sys.path lines find script_utils. Imports run one
way, so this module prints nothing of its own except the verb's held output, which it replays when the verb ends: a
caller of state_transaction names the function that reports a state file that changed under the verb."""
import contextlib
import dataclasses
import io
import json
import os
import pathlib
import re
import sys

import script_utils
from code_step_state import RunState, StateFileError

RUNS_DIR_NAME = "runs"
SESSION_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]+")
STATE_FILE_NAME = "state.json"
STATE_DIRS = {}  # resolved folder -> the code-step state folder git named for it
# The state files of the verbs running in this process, one dict per open verb: resolved path -> VerbStateFile.
OPEN_VERBS = []


def state_dir(cwd):
    # One verb asks for the state folder many times: git names it once per resolved folder.
    resolved_cwd = os.path.realpath(cwd)
    if resolved_cwd in STATE_DIRS:
        return STATE_DIRS[resolved_cwd]

    found = script_utils.git_path(cwd, "code-step")
    if found is None:
        return None
    STATE_DIRS[resolved_cwd] = found
    return STATE_DIRS[resolved_cwd]


def state_file(cwd):
    return state_dir(cwd) / STATE_FILE_NAME


@dataclasses.dataclass
class VerbStateFile:
    """A state file as the open verb has left it so far. `found` is its text on disk at the verb's first touch and
    `kept` the text the verb leaves; None in either means no file. `saved_from` and `session_id` come from the verb's
    last save, for the session's list of repos."""
    found: str | None
    kept: str | None
    saved_from: pathlib.Path | str | None = None
    session_id: str | None = None


def verb_state_file(path):
    # None outside a verb. Inside one, the first touch reads the file from disk, and every later load, save and drop
    # works on what the verb holds until state_transaction writes it at the verb's end.
    if not OPEN_VERBS:
        return None

    verb_files = OPEN_VERBS[-1]
    resolved_path = path.resolve()
    if resolved_path not in verb_files:
        disk_text = state_text_on_disk(resolved_path)
        verb_files[resolved_path] = VerbStateFile(found=disk_text, kept=disk_text)
    return verb_files[resolved_path]


def state_text_on_disk(path):
    try:
        return path.read_text()
    except (FileNotFoundError, NotADirectoryError):
        return None


def load_state(cwd):
    directory = state_dir(cwd)
    if directory is None:
        return None
    return read_state_file(directory)


def read_state_file(directory):
    # Inside a verb, the state as the verb has left it so far; elsewhere, the state on disk.
    path = directory / STATE_FILE_NAME
    verb_file = verb_state_file(path)
    if verb_file is None:
        disk_text = state_text_on_disk(path)
        return parse_state_text(disk_text, path)
    return parse_state_text(verb_file.kept, path)


def parse_state_text(text, path):
    if text is None:
        return None
    try:
        raw = json.loads(text)
    except ValueError:
        raise StateFileError(f"{path} is not readable JSON") from None
    return RunState.from_json(raw, path)


def load_aborted_plan_state(cwd):
    # The newest archived state of an aborted run, or None when it is unreadable, names no plan, or a run started after
    # the abort. `abort` archives the state under a UTC timestamp name, so the last name in sort order is the latest.
    directory = state_dir(cwd)
    if directory is None:
        return None

    archives = sorted(directory.glob("aborted-*.json"), reverse=True)
    if not archives:
        return None

    newest = archives[0]
    try:
        raw = json.loads(newest.read_text())
        archived = RunState.from_json(raw, newest)
    except (OSError, ValueError, StateFileError):
        return None
    if not archived.plan:
        return None
    if started_after_abort(directory, archived.run_id):
        return None
    return archived


def started_after_abort(directory, archived_run_id):
    # `start` clears the run folders of older runs before it logs its own, so a run folder other than the archived
    # run's means a later start.
    folder = directory / RUNS_DIR_NAME
    if not folder.is_dir():
        return False
    return any(run_folder.name != archived_run_id for run_folder in folder.iterdir())


def state_text(state):
    return json.dumps(state.to_json(), indent=1)


def save_state(cwd, state):
    # Inside a verb, the file is written at the verb's end; elsewhere, at once.
    path = state_file(cwd)
    saved_text = state_text(state)
    verb_file = verb_state_file(path)
    if verb_file is None:
        write_state_text(path, saved_text, cwd, state.session_id)
        return

    verb_file.kept = saved_text
    verb_file.saved_from = cwd
    verb_file.session_id = state.session_id


def drop_state(cwd):
    # Inside a verb, the file goes at the verb's end; elsewhere, at once.
    path = state_file(cwd)
    verb_file = verb_state_file(path)
    if verb_file is None:
        path.unlink(missing_ok=True)
        return

    verb_file.kept = None


def write_state_text(path, text, cwd, session_id):
    path.parent.mkdir(parents=True, exist_ok=True)
    script_utils.write_text_atomically(path, text)

    register_session_repo(cwd, session_id)


@contextlib.contextmanager
def state_transaction(report_changed_state_files):
    """Runs one verb as one change. Its saves and drops of a state file stay in memory and what it prints is held.
    When it returns, each state file it changed is written once, atomically, and then its output prints. A verb that
    raises, or exits with an error, saves no state file and prints nothing it held. Files it wrote on the way (say.md,
    question.md, the run log, handback_store rows, dispatch prompts, plan edits, the detached review script) stay.
    sys.exit(0) counts as a return."""
    verb_files = {}
    held_output = io.StringIO()
    OPEN_VERBS.append(verb_files)
    clean_exit = None
    try:
        with contextlib.redirect_stdout(held_output):
            yield
    except SystemExit as exited:
        if exited.code not in (None, 0):
            raise
        clean_exit = exited
    finally:
        OPEN_VERBS.pop()

    finish_verb(verb_files, held_output.getvalue(), report_changed_state_files)
    if clean_exit is not None:
        raise clean_exit


def finish_verb(verb_files, held_output, report_changed_state_files):
    # A state file that changed on disk while the verb ran (an `abort`, which takes no lock) stays as it is: the verb
    # saves no state file, and its output, which rests on the old state, is dropped. A verb that drops the file is never
    # held back, so an abort always ends the run.
    changed_paths = [path for path, verb_file in verb_files.items()
                     if verb_file.kept is not None and state_text_on_disk(path) != verb_file.found]
    if changed_paths:
        report_changed_state_files(changed_paths)
        return

    for path, verb_file in verb_files.items():
        write_verb_state_file(path, verb_file)
    sys.stdout.write(held_output)


def write_verb_state_file(path, verb_file):
    # A dropped file goes and a saved one is written; a file the verb only read stays as it is.
    if verb_file.kept is None:
        path.unlink(missing_ok=True)
        return
    if verb_file.saved_from is not None:
        write_state_text(path, verb_file.kept, verb_file.saved_from, verb_file.session_id)


def session_repos_file(session_id):
    # The list of repos whose /code state a session pinned, or None for an id that is not a plain name. A hook event
    # carries the session's cwd, which is another checkout when /code runs in a worktree, so the hooks read this list.
    if not isinstance(session_id, str) or not SESSION_ID_PATTERN.fullmatch(session_id):
        return None
    return pathlib.Path.home() / ".claude" / "state" / "code-step-sessions" / session_id


def session_repo_dirs(session_id):
    # The repos the session pinned that still exist, in the order it pinned them.
    repos_file = session_repos_file(session_id)
    if repos_file is None:
        return []
    try:
        listed = repos_file.read_text().splitlines()
    except OSError:
        return []
    return [repo for repo in listed if repo and pathlib.Path(repo).is_dir()]


def register_session_repo(cwd, session_id):
    repos_file = session_repos_file(session_id)
    if repos_file is None:
        return

    repo = str(pathlib.Path(cwd).resolve())
    if repo in session_repo_dirs(session_id):
        return
    repos_file.parent.mkdir(parents=True, exist_ok=True)
    with repos_file.open("a") as listing:
        listing.write(repo + "\n")
