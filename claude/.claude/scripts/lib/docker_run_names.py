"""Which `docker run` steps of one shell command carry no container name, and the fixed form of each.

An unnamed container gets a random name, so nothing ties it to a ticket or a session, and one that hangs keeps running
unseen. The fixed form names it `<ticket>-<purpose>` and removes it at exit. `docker compose run` is not read: compose
names its containers.

Owner of the docker and podman `run` name check: import it, never add a second copy.

Known limit: the image is found by `shell_command.container_run`, which skips the value of each option in
DOCKER_VALUE_OPTIONS. A missing global option skips the whole call; a missing run option reads its value as the image.
A trailing `&` is not part of the step text, so the fixed form leaves it off. A run inside backticks or inside a
double-quoted `$( ... )` is never read, so the gate passes it. When the call's words and image match the step text in
zero places or in more than one place, the fixed form is rebuilt from the words, drops the step's redirections, and cuts
an outer run's `$( ... )` to `$`: `docker run img echo docker run img > o` loses its `> o`.
"""
import os
import re
from typing import NamedTuple

import plan_format
import script_utils
import shell_command
import shell_command_words
import shell_statements
import shell_steps

NAME_OPTION = "--name"
REMOVE_OPTION = "--rm"
REMOVE_TRUE = "--rm=true"
REMOVE_PREFIX = REMOVE_OPTION + "="
HELP_OPTION = "--help"
TICKET_PLACEHOLDER = "<ticket>"
PURPOSE_PLACEHOLDER = "<purpose>"
BRANCH_TICKET = re.compile(rf"^({plan_format.TICKET_KEY})")


class RunSpan(NamedTuple):
    """Word positions of one run step in its raw words: `first` is the count of leading group words (`do`, `then`,
    `{`), so it is where the step's command starts, wrappers such as `sudo` or `env` included; `run_end` is the index
    after `run`; `image_end` is the index of the image (the words between `run_end` and `image_end` are the run's
    options)."""
    first: int
    run_end: int
    image_end: int


class NameWord(NamedTuple):
    """One `--name` option among the option words: where it starts, how many words it takes, and its value."""
    start: int
    width: int
    value: str


def find_container_run(raw_words):
    """(command_index, ContainerRun) of the docker or podman `run` call behind any wrappers, the indexes counted in
    raw_words and the run's own indexes counted from the program word; None when the words are no such call."""
    unquoted = [shell_command_words.unquoted_word(word) for word in raw_words]
    for name in shell_command.CONTAINER_PROGRAMS:
        command_index = shell_command_words.command_word_index(raw_words, name)
        if command_index is None:
            continue
        # command_word_index proved the word names the program, so a path such as /usr/bin/docker reads as `name`.
        run = shell_command.container_run([name, *unquoted[command_index + 1 :]])
        if run is not None:
            return command_index, run
    return None


def name_words(options):
    """Each `--name <value>` or `--name=<value>` option among the option words, in order."""
    found = []
    index = 0
    while index < len(options):
        word = options[index]
        if word.startswith(NAME_OPTION + "="):
            found.append(NameWord(index, 1, word[len(NAME_OPTION) + 1:]))
            index += 1
        elif word == NAME_OPTION and index + 1 < len(options):
            found.append(NameWord(index, 2, options[index + 1]))
            index += 2
        elif word == NAME_OPTION:
            found.append(NameWord(index, 1, ""))
            index += 1
        else:
            index += 1
    return found


def names_container(options):
    """True when the last `--name` option, the one docker keeps, has a value that is not empty."""
    found = name_words(options)
    return bool(found) and found[-1].value != ""


def branch_ticket(directory):
    """The leading `KEY-123` of the branch checked out in `directory`; the placeholder when there is none or the
    folder is unknown (None)."""
    if directory is None:
        return TICKET_PLACEHOLDER
    branch = script_utils.current_branch(directory) or ""
    matched = BRANCH_TICKET.match(branch)
    if matched is None:
        return TICKET_PLACEHOLDER
    return matched.group(1)


def leading_group_word_count(raw_words):
    """How many words at the start open the step (`do`, `then`, `{`) without being part of the docker command."""
    count = 0
    while count < len(raw_words) and raw_words[count] in shell_command.GROUP_WORDS:
        count += 1
    return count


def dropped_option_indexes(options):
    """Indexes among the options of the words the fixed form leaves out: every `--name` option, which would override
    the inserted name, and each `--rm=<value>` word but `--rm=true`, which the inserted `--rm` replaces."""
    dropped = set()
    for found in name_words(options):
        dropped.update(range(found.start, found.start + found.width))
    for index, word in enumerate(options):
        if word.startswith(REMOVE_PREFIX) and word != REMOVE_TRUE:
            dropped.add(index)
    return dropped


def fixed_form(step, raw_words, span, directory):
    """The step's own text from the first word after the leading group words (`do`, `then`, `{`), so wrappers such as
    `timeout 60` stay in the form, with `--rm --name <ticket>-<purpose>` inserted right after
    `run`, so redirections, quoting and `$( ... )` words survive. `--rm` is inserted unless the options hold `--rm` or
    `--rm=true`; every `--name` option and each other `--rm=<value>` word is left out, as it would override the
    inserted one. When the step text does not match the resolved raw words, the form is built from those words
    joined by single blanks, and the step's redirections are left out. The same holds when the call's words and image
    match the step text in more than one place (`docker run img $(docker run img)`); for the outer call that form
    ends at a cut-off `$`, a known limit."""
    option_raw_words = raw_words[span.run_end:span.image_end]
    options = [shell_command_words.unquoted_word(word) for word in option_raw_words]
    dropped = dropped_option_indexes(options)
    inserted = []
    if REMOVE_OPTION not in options and REMOVE_TRUE not in options:
        inserted.append(REMOVE_OPTION)
    inserted.append(NAME_OPTION)
    inserted.append(f"{branch_ticket(directory)}-{PURPOSE_PLACEHOLDER}")
    kept_indexes = [index for index in range(len(option_raw_words)) if index not in dropped]
    # One group per word up to the image, so a dropped word is cut by its own position in the text.
    pattern = r"\s+".join("(" + re.escape(word) + ")" for word in raw_words[span.first:span.image_end])
    # The image word after the options tells an outer run from the run nested in its `$( )`.
    if span.image_end < len(raw_words):
        pattern += r"(?=\s+" + re.escape(raw_words[span.image_end]) + r"(?=[\s;&|()<>`]|$))"
    prefix = re.compile(pattern)
    text = step.strip()
    matches = list(prefix.finditer(text))
    # With more than one match the text cannot say which one is this call (the same words and image in an outer run
    # and the run nested in its `$( )`), so the form is built from the resolved words.
    matched = matches[0] if len(matches) == 1 else None
    if matched is None:
        kept = [option_raw_words[index] for index in kept_indexes]
        rebuilt = " ".join(raw_words[span.first:span.run_end] + inserted + kept + raw_words[span.image_end:])
        return shell_command_words.before_subshell_closer(rebuilt)
    run_group = span.run_end - span.first
    head = text[matched.start():matched.end(run_group)]
    kept = [matched.group(run_group + 1 + index) for index in kept_indexes]
    tail = shell_command_words.before_subshell_closer(text[matched.end():])
    return head + " " + " ".join(inserted + kept) + tail


def names_container_program(word):
    """True when the word is the docker or podman command, by its basename."""
    return any(shell_command_words.word_names_command(word, name) for name in shell_command.CONTAINER_PROGRAMS)


def unnamed_docker_runs(command, directory):
    """The fixed form of each docker or podman `run` step of the command that names no container, `directory` being
    where the command starts. A `--help` call starts no container and is left out. This check fails open: a step the
    shell reader cannot parse is reported on stderr and skipped."""
    code = shell_statements.shell_code(command)
    placed_calls = shell_steps.placed_commands(code, os.path.abspath(directory), peel_containers=False,
                                               skip_unread=True)
    forms = []
    for placed in placed_calls:
        if not placed.words or not names_container_program(placed.words[0]):
            continue
        raw_words = shell_command_words.placed_raw_words(placed)
        found = find_container_run(raw_words)
        if found is None:
            continue
        command_index, run = found
        run_end = command_index + run.run_index + 1
        image_end = command_index + run.image_index
        options = [shell_command_words.unquoted_word(word) for word in raw_words[run_end:image_end]]
        if HELP_OPTION in options or names_container(options):
            continue
        span = RunSpan(leading_group_word_count(raw_words), run_end, image_end)
        forms.append(fixed_form(placed.step, raw_words, span, placed.directory))
    return forms
