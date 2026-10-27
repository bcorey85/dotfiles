"""code_step_start_args.py: what `start` reads from its arguments besides the plain flags: the task file, the run notes
that follow a plan and its phase, and a plan file outside the repo.

Imports run one way: code_step_core, code_step_start_args, code_step."""
import os
import pathlib
import re
import shlex

import plan_format
import script_utils
from code_step_core import TICKET_ID, script_command


class TaskFileError(Exception):
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


def is_plan_reference(word):
    return (word.endswith(".md") and os.path.isfile(word)) or TICKET_ID.match(word) is not None


def carry_run_notes(parsed):
    # A phase run's text after the plan is its run notes. `<plan file or ticket id> [--phase <id> | Phase <id>] <text>`
    # comes back with the plan, the phase and the notes set and no task text. Any other text stays task text.
    if not parsed.positional_words:
        return parsed

    words = script_utils.words_of_arguments(parsed.positional_words)
    plan_words, text_words, phase_id, _ = split_plan_words(words, parsed)
    if phase_id is None:
        phase_id, text_words = leading_phase_words(text_words)

    if phase_id is None or not plan_words or not all(is_plan_reference(word) for word in plan_words):
        return parsed

    run_notes = " ".join(text_words) or None
    return parsed._replace(plan_args=plan_words, phase_id=phase_id, task_text=None, positional_words=None,
                           run_notes=run_notes)


def run_notes_lines(run_notes):
    # The coder brief's lines for the user's run notes.
    if not run_notes:
        return []

    return ["", "Run notes from the user. They bind this run; the plan stays the spec:", run_notes]


def outside_repo_plan_refusal(repo_dir, parsed):
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
    command = script_command(shlex.join(["start", *modifier_words, "--task-file", str(plan_path)]))
    return (f"{plan_path} is outside the repo and is not a plan.", [command],
            ("The command reads the file as the task text. A plan file has to be inside the repo.",))
