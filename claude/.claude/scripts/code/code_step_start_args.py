"""code_step_start_args.py: what `start` reads from its arguments besides the plain flags: the task file, the run notes
that follow a plan and its phase or a plan with no phase, and a plan file outside the repo.

Imports run one way: code_step_core, code_step_start_args, code_step."""
import os
import pathlib
import re
import shlex

import plan_format
import script_utils
from code_step_core import TICKET_ID, script_command

# Every flag `start` reads besides --help. --task makes the rest of the words task text; a value
# flag takes the next word as its value.
TASK_FLAG = "--task"
VALUE_FLAGS = ("--task-file", "--phase", "--repo")
SWITCH_FLAGS = ("--restart", "--headless", "--coder-stopped")
START_MODIFIERS = ("+fast", "+deep")
START_FLAGS = (TASK_FLAG, *VALUE_FLAGS, *SWITCH_FLAGS, *START_MODIFIERS)


def looks_like_plan_argument(word):
    # A word with whitespace is task text that happens to name a file, unless it is itself a file (a real plan whose
    # path has a space). Words are tested with os.path, not pathlib: before Python 3.14, pathlib raises on a word
    # longer than a file name may be, which is any long task text.
    if script_utils.has_whitespace(word) and not os.path.isfile(word):
        return False

    return (looks_like_plan_path(word) or TICKET_ID.match(word) is not None or os.path.isfile(word)
            or os.path.isdir(word))


def looks_like_plan_path(argument):
    return "/" in argument or argument.endswith(".md")


def is_flag(word):
    return word.startswith("-") and len(word) > 1


def starts_task_text(word):
    return word not in START_MODIFIERS and not is_flag(word) and not looks_like_plan_argument(word)


def flag_words_end(args):
    # Where the flags end: at `--task` or at the first word that starts task text, the point parse_start_args stops
    # reading flags. The value after --task-file, --phase and --repo is not a word that starts the text.
    position = 0
    while position < len(args):
        word = args[position]
        if word == TASK_FLAG:
            return position
        if word in VALUE_FLAGS:
            position += 2
            continue
        if starts_task_text(word):
            return position
        position += 1

    return len(args)


class TaskFileError(Exception):
    pass


class RepoFlagError(Exception):
    pass


def read_task_file(args, flag_position):
    # The text of the file named after `--task-file`, byte for byte: no shell quoting reaches it.
    if flag_position + 1 >= len(args):
        raise TaskFileError("--task-file needs a path")

    path_text = args[flag_position + 1]
    try:
        task_text = pathlib.Path(path_text).read_text()
    except (OSError, UnicodeDecodeError) as error:
        raise TaskFileError(f"cannot read the task file {path_text}: {error}") from None

    if not task_text.strip():
        raise TaskFileError(f"the task file {path_text} is empty")
    return task_text


TASK_FILE_REPO_LINE = re.compile(r"^Repo(?: root)?:[ \t]*(\S.*?)[ \t]*$")


def split_quoted_flags(args):
    # The args /code receives as one string, `--task "<text>"` or `+deep --task <text>`, as the words the shell would
    # have given. Any other args come back as they were.
    if len(args) != 1 or not args[0].startswith(START_FLAGS) or not script_utils.has_whitespace(args[0]):
        return args

    try:
        return shlex.split(args[0])
    except ValueError:
        return args[0].split()


def task_file_repo(args):
    # The path on the `Repo:` or `Repo root:` line that opens the task file named by `--task-file`, or None.
    flag_stops_at = flag_words_end(args)
    if "--task-file" not in args[:flag_stops_at]:
        return None

    flag_position = args.index("--task-file")
    try:
        task_text = read_task_file(args, flag_position)
    except TaskFileError:
        return None

    first_line = next((line for line in task_text.splitlines() if line.strip()), "")
    repo_line = TASK_FILE_REPO_LINE.match(first_line)
    return repo_line.group(1) if repo_line else None


def start_repo_path(args):
    # The checkout `start` runs in: the path after `--repo` (before any `--task` text), else the `Repo:` line of the
    # task file, else None for the current directory. A `--repo` with no path, or a flag in its place, raises.
    flag_stops_at = flag_words_end(args)
    for position, word in enumerate(args[:flag_stops_at]):
        if word != "--repo":
            continue

        if position + 1 >= len(args) or args[position + 1].startswith("-"):
            raise RepoFlagError("--repo needs a path")
        return args[position + 1]

    return task_file_repo(args)


def absolute_path_args(args):
    # The args with the path after `--task-file` and after `--repo` (before any `--task` text) made absolute against
    # the current directory, so they still name the same files once `start` moves to another checkout.
    flag_stops_at = flag_words_end(args)
    absolute = list(args)
    for position, word in enumerate(args[:flag_stops_at]):
        is_path_next = position + 1 < flag_stops_at and not args[position + 1].startswith("-")
        if word in ("--task-file", "--repo") and is_path_next:
            absolute[position + 1] = os.path.abspath(args[position + 1])

    return absolute


def phase_flag_position(words):
    # Where an explicit `--phase <phase id>` sits in the words, or None. A `--phase` with no word after it, or with a
    # word that is not a phase id after it, is part of the text.
    for index, word in enumerate(words):
        is_last = index + 1 >= len(words)
        if word == "--phase" and not is_last and re.fullmatch(plan_format.PHASE_ID, words[index + 1]):
            return index

    return None


def split_plan_words(words, parsed):
    # (plan words, task words, phase id, whether the text held a `--phase <id>`) for task text that may hold a plan.
    # Only a plan file as the first word, a plan argument before the text, or an explicit --phase is not task text.
    plan_words = list(parsed.plan_args)
    is_plan_file_first = not plan_words and os.path.isfile(words[0])
    if is_plan_file_first:
        plan_words = [words[0]]
    text_words = words[1:] if is_plan_file_first else list(words)
    phase_id = parsed.phase_id
    phase_flag_at = phase_flag_position(text_words)
    if phase_flag_at is not None:
        phase_id = text_words[phase_flag_at + 1]
        del text_words[phase_flag_at:phase_flag_at + 2]
    return plan_words, text_words, phase_id, phase_flag_at is not None


def leading_phase_words(words):
    # (phase id, the words after it) for words that start with `Phase <id>`; (None, the words) for any other.
    is_phase_words = len(words) >= 2 and words[0].lower() == "phase" and re.fullmatch(plan_format.PHASE_ID, words[1])
    if not is_phase_words:
        return None, words

    return words[1], words[2:]


def has_phase_status_entries(path):
    # Whether the file parses to at least one Phase Status entry, so a README or a brief is not taken for a plan.
    try:
        plan = plan_format.parse_plan_with_closing_phases(pathlib.Path(path).read_text().splitlines())
    except (OSError, UnicodeDecodeError):
        return False

    return bool(plan["entries"])


def is_plan_reference(word):
    return script_utils.is_existing_md_file(word) or TICKET_ID.match(word) is not None


def is_plan_file_in_repo(word):
    # A plan file inside the current directory (`start` has moved to the repo) that parses to Phase Status entries.
    # With no phase, a plan outside the repo is not carried: the refusal that says the text after the plan is not
    # task text keeps it. With a phase it is carried, and the question that asks for a plan inside the repo names
    # the notes.
    if not script_utils.is_existing_md_file(word):
        return False

    is_inside_repo = pathlib.Path(word).resolve().is_relative_to(pathlib.Path.cwd())
    if not is_inside_repo:
        return False

    return has_phase_status_entries(word)


def carry_run_notes(parsed, saved_plan=None):
    # A phase run's text after the plan is its run notes. `<plan file or ticket id> [--phase <id> | Phase <id>] <text>`
    # comes back with the plan, the phase and the notes set and no task text.
    # `<plan file inside the repo that has phases> <text>` with no phase does the same for the plan's next phase; a
    # ticket id with no phase may be the first word of a task, so its text stays task text.
    # An explicit `--phase <id>` with no plan named takes the saved plan. Any other text stays task text.
    if not parsed.positional_words:
        return parsed

    words = script_utils.words_of_arguments(parsed.positional_words)
    plan_words, text_words, phase_id, _ = split_plan_words(words, parsed)
    if not plan_words and phase_id is not None and saved_plan:
        plan_words = [saved_plan]
    if phase_id is None:
        phase_id, text_words = leading_phase_words(text_words)

    if len(plan_words) != 1 or not is_plan_reference(plan_words[0]):
        return parsed
    if phase_id is None and not is_plan_file_in_repo(plan_words[0]):
        return parsed

    run_notes = " ".join(text_words) or None
    return parsed._replace(plan_args=plan_words, phase_id=phase_id, task_text=None, positional_words=None,
                           run_notes=run_notes)


def run_notes_lines(run_notes):
    # The coder brief's lines for the user's run notes.
    if not run_notes:
        return []

    return ["", "Run notes from the user. They bind this run; the plan stays the spec:", run_notes]


def outside_repo_plan_refusal(repo_dir, parsed, repo_flags):
    # (reason, commands, notes) for a first plan argument that is a file outside the repo and is no plan, or None. A
    # plan is kept by its path in the repo, so a file outside it can only be task text: the rerun reads it as that. A
    # file that parses as a plan goes on to the stop that asks for a plan inside the repo.
    if parsed.task_text is not None or not parsed.plan_args or not os.path.isfile(parsed.plan_args[0]):
        return None

    plan_path = pathlib.Path(parsed.plan_args[0])
    if plan_path.resolve().is_relative_to(repo_dir):
        return None

    try:
        plan = plan_format.parse_plan_with_closing_phases(plan_path.read_text().splitlines())
    except (OSError, UnicodeDecodeError):
        return None

    if plan["entries"] or plan["sections"]:
        return None

    modifier_words = [parsed.modifier] if parsed.modifier else []
    command = script_command(shlex.join(["start", *repo_flags, *modifier_words, "--task-file", str(plan_path)]))
    return (f"{plan_path} is outside the repo and is not a plan.", [command],
            ("The command reads the file as the task text. A plan file has to be inside the repo.",))
