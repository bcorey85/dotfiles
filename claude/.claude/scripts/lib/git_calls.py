"""The git calls a Bash command makes, and the directory each runs in.

Calls are read in command position, after git's own options (`-C <dir>`, `-c <key=value>`, `--no-pager`) and wrapper
words (env, timeout), and inside `$(...)` and backticks. Heredoc bodies, comments and quoted strings are text, not
calls, except that a `$(...)` or backtick span is still read as a call inside quotes, single or double (the shell
runs it only inside double quotes; the gate deliberately over-reads the single-quoted form). A call's
directory is its `-C` directory, taken relative to the target of an earlier `cd` in the same command, else to the
starting directory. A command with a `cd` after a `(` not preceded by `$` (SUBSHELL_CD matches such a `(` before a
`cd`, quoted or not) follows no `cd`, and a quoted, variable or
substituted target is not read: the call is marked unplaced (`placed` False), as is one that follows a `cd` the gate
does not follow (subshell, `pushd`, `popd`, `builtin cd`, `command cd`, `{ cd`, a `cd` that runs only on a
condition or in a pipeline or background, a `cd` in code-runner text), one run through an `env -C`, `env --chdir`,
`sudo -D` or `sudo --chdir` wrapper, one read from code-runner or launcher text, one with `-c core.worktree` or a
`--config-env` option, and one with a GIT_DIR, GIT_WORK_TREE, GIT_COMMON_DIR, CDPATH, HOME, GIT_CONFIG_COUNT,
GIT_CONFIG_PARAMETERS, GIT_CONFIG_GLOBAL, GIT_CONFIG_SYSTEM or GIT_CONFIG assignment anywhere in the command
(calls inside `$(...)` included).
`is_linked_worktree` reads an unplaced call as a main checkout and asks git (`rev-parse`) about a placed one.
A command that names a code runner
(`bash -c`, eval, xargs, ssh) is read as text: every `git` word in it starts a call.
"""
import os
import re
import subprocess
import sys
from typing import NamedTuple

import shell_command
import shell_directory
import shell_statements
import shell_steps

# The text of one git call inside code the gate cannot parse: from the `git` word to a separator or a quote.
GIT_CALL_TEXT = re.compile(r"\bgit\b[^\n;&|'\"`()]*", re.I)
SUBSHELL_CD = re.compile(r"(?<!\$)\(.*\bcd\b", re.S)
STACK_MOVE_WORDS = tuple(word for word in shell_directory.DIRECTORY_MOVE_WORDS if word != shell_directory.CD_WORD)
PUSHD_OR_POPD = re.compile(r"\b(?:" + "|".join(STACK_MOVE_WORDS) + r")\b")
CD_WORD_PATTERN = re.compile(r"\b" + shell_directory.CD_WORD + r"\b")
# Words in front of a statement's real command: a `cd` behind one of them is not followed.
DIRECTORY_MOVE_PREFIXES = ("{", "builtin", "command", "while", "until", "!")
CD_OPTIONS = ("-L", "-P", "-e", "-@", "--")
# A path word holding one of these is a quoted string, a variable, a substitution or a glob the gate cannot read.
UNREAD_PATH_MARKS = ('"', "'", "$", "`", "*", "?")
# An assignment that moves the repo (`GIT_DIR=x git ...`, `env GIT_WORK_TREE=x git ...`, `export GIT_DIR=x`).
REPO_ENVIRONMENT_NAMES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR")
# An assignment that moves where a `cd` lands (CDPATH, HOME) or sets git config the gate does not read (a
# GIT_CONFIG_COUNT or GIT_CONFIG_PARAMETERS pair can set core.worktree; GIT_CONFIG_GLOBAL, GIT_CONFIG_SYSTEM and
# GIT_CONFIG name a file the command can write first): the call is unplaced, like REPO_ENVIRONMENT_NAMES.
CONFIG_ENVIRONMENT_NAMES = ("GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM",
                            "GIT_CONFIG")
PLACEMENT_ENVIRONMENT_NAMES = (*REPO_ENVIRONMENT_NAMES, "CDPATH", "HOME", *CONFIG_ENVIRONMENT_NAMES)
PLACEMENT_ENVIRONMENT = re.compile(r"\b(?:" + "|".join(PLACEMENT_ENVIRONMENT_NAMES) + ")=")
CONFIG_ENVIRONMENT = re.compile(r"\b(?:" + "|".join(CONFIG_ENVIRONMENT_NAMES) + ")=")
# Statement heads that open and close a compound command whose body runs only on a condition or in a loop.
BLOCK_OPENERS = {"if", "case", "for", "select", "while", "until"}
BLOCK_CLOSERS = {"fi", "esac", "done"}
# A step after or before a `|` (or `|&`) runs in a subshell, so a `cd` there does not move the shell. A step after a `&`
# is read as conditional too: the gate does not track which list the `&` ended, so it fails closed. (`|&` stays inside
# its step: a step that holds one is a pipeline.)
SUBSHELL_OPERATORS = {"|", "&"}
# The characters read_part strips before a pipe part's first word: shell_steps.STEP_OPENERS without `{`, because a
# `{ cd` group is a move the gate does not follow, so its `{` must stay a word.
PART_OPENERS = shell_steps.STEP_OPENERS.replace("{", "")
# The path component that stands for a `-C` or `cd` target the gate cannot read.
UNREAD_DIRECTORY = "<unread>"
REV_PARSE_TIMEOUT_SECONDS = 10
# The config value of a key set by `--config-env key=VAR`: only the key is known, the value is read from the
# environment at run time. It is in no false set, so every value reader counts the key as set.
CONFIG_FROM_ENVIRONMENT = "<from-env>"


class CommandContext(NamedTuple):
    """What the command around a git call does. `environment_moves_placement` is True when it assigns a name in
    PLACEMENT_ENVIRONMENT_NAMES. `environment_sets_config` is True when it assigns a name in
    CONFIG_ENVIRONMENT_NAMES. `from_code_text` is True for words cut out of code-runner or launcher text, whose
    directory and arguments the runner may rewrite: the call is unplaced. `unfollowed_move` is True when it moves
    its directory in a way the gate does not follow (see `has_unfollowed_directory_move`): the call is unplaced."""
    environment_moves_placement: bool = False
    unfollowed_move: bool = False
    environment_sets_config: bool = False
    from_code_text: bool = False


NO_CONTEXT = CommandContext()


class GitCall(NamedTuple):
    subcommand: str
    arguments: list
    config: dict
    directory: str
    # The `--git-dir` and `--work-tree` option values, joined to the directory; None when the call has none.
    git_dir: str | None = None
    work_tree: str | None = None
    # False when the gate cannot tell which repo the call acts on: a `-C`, `cd`, `--git-dir` or `--work-tree` value it
    # cannot read, a `cd` it does not follow, an `env -C` or `sudo -D` wrapper, text read from a code runner or
    # launcher, a `cd -`, `-c core.worktree`, `--config-env`, or an assignment named in
    # PLACEMENT_ENVIRONMENT_NAMES.
    placed: bool = True
    # True when the command assigns GIT_CONFIG_COUNT, GIT_CONFIG_PARAMETERS, GIT_CONFIG_GLOBAL, GIT_CONFIG_SYSTEM or
    # GIT_CONFIG, which can set any config key.
    environment_sets_config: bool = False


def has_unread_mark(path):
    return any(mark in path for mark in UNREAD_PATH_MARKS)


def readable_directory(directory):
    """The directory with everything from the first UNREAD_DIRECTORY component on dropped: the last folder the gate
    could read, where a call with an unread target is judged for branch and commit rules."""
    parts = directory.split(os.sep)
    if UNREAD_DIRECTORY not in parts:
        return directory
    readable = os.sep.join(parts[:parts.index(UNREAD_DIRECTORY)])
    if readable:
        return readable
    return os.sep if directory.startswith(os.sep) else "."


def option_path(options, name, directory):
    """The path the last `name` option of git's own options gives, in `--name value` or `--name=value` form, joined to
    `directory`; None when there is none."""
    values = list(shell_command.git_option_values(options, name))
    if not values:
        return None
    return os.path.join(directory, os.path.expanduser(values[-1]))


def joined_directory(directory, target):
    """The directory `cd <target>` or `git -C <target>` moves to from `directory`; `directory` when the target is empty.
    A target the gate cannot read, or that starts with `-`, adds the UNREAD_DIRECTORY component, which
    every later join keeps, so `git_call` can tell that the repo is not placed."""
    if not target:
        return directory
    # `cd` options are stripped before this call, so a target that starts with `-` is a folder named so.
    if target.startswith("-") or has_unread_mark(target):
        return os.path.join(directory, UNREAD_DIRECTORY)
    expanded_target = os.path.expanduser(target)
    return os.path.join(directory, expanded_target)


def readable_option_words(resolved_words, blanked_words):
    """The resolved words, with each word that held a quote or an escape cut down to what the gate can read: a word
    that is not an option name becomes `""` (unread), and a quoted `--name=value` keeps its name with the value `""`."""
    words = []
    for resolved, blanked in zip(resolved_words, blanked_words, strict=True):
        if blanked == resolved:
            words.append(resolved)
            continue
        name, equals, _value = resolved.partition("=")
        if resolved.startswith("-") and equals:
            words.append(name + '=""')
        elif resolved.startswith("-"):
            words.append(resolved)
        else:
            words.append('""')
    return words


def config_env_pairs(options):
    """{lowercased key: lowercased variable name} for each `--config-env key=VAR` or `--config-env=key=VAR` option."""
    pairs = {}
    for setting in shell_command.git_option_values(options, "--config-env"):
        key, _equals, variable = setting.partition("=")
        pairs[key.lower()] = variable.lower()
    return pairs


def call_is_placed(context, wrapper_moves, directory_is_unread, option_paths, config, config_env_settings):
    """True when the gate knows which folder the call runs in: nothing around it, in its wrapper words or in its
    `--git-dir`/`--work-tree` values (`option_paths`) moves or hides the folder."""
    option_values_are_unread = any(has_unread_mark(option_path or "") for option_path in option_paths)
    moves_work_tree_by_config = "core.worktree" in config or bool(config_env_settings)
    return not (context.environment_moves_placement or wrapper_moves or directory_is_unread
                or option_values_are_unread or context.from_code_text or context.unfollowed_move
                or moves_work_tree_by_config)


def git_call(words, directory=".", context=NO_CONTEXT, resolved_words=None):
    """The GitCall the words run from `directory`, once wrapper words and git's own options are dropped; None when
    they run no git subcommand. `context` is what the command around the words does (see `CommandContext`).
    `resolved_words` are the same words with the quotes and escapes removed: the wrapper, the `git`
    word, git's options, the subcommand and the arguments are read from them, so a quoted word counts; the
    `-C`, `--git-dir` and `--work-tree` values are read only when unquoted, so a quoted target stays unread."""
    if resolved_words is None:
        resolved_words = words
    wrapper_moves = shell_command.wrapper_moves_directory(resolved_words)
    argument_words = shell_command.command_after_wrappers(resolved_words)
    if not argument_words or os.path.basename(argument_words[0]).lower() != "git":
        return None
    # The wrappers drop leading words only, so the tail of the blanked words lines up with the resolved ones.
    words = words[len(words) - len(argument_words):]

    config = {}
    options, index = shell_command.git_options(argument_words)
    for key, setting in shell_command.git_c_settings(options).items():
        config[key] = setting.lower()
    config_env_settings = config_env_pairs(options)
    for key in config_env_settings:
        config[key] = CONFIG_FROM_ENVIRONMENT
    # The option names are read from the resolved words, so a quoted or escaped `-C` counts; a quoted value stays
    # unread.
    option_words = readable_option_words(argument_words, words)
    directory_options, _directory_index = shell_command.git_options(option_words)
    for option, value in directory_options:
        if option == "-C" and value is not None:
            directory = joined_directory(directory, value)
    if index == len(argument_words):
        return None
    directory_is_unread = UNREAD_DIRECTORY in directory.split(os.sep)
    directory = readable_directory(directory)
    git_dir = option_path(directory_options, "--git-dir", directory)
    work_tree = option_path(directory_options, "--work-tree", directory)
    placed = call_is_placed(context, wrapper_moves, directory_is_unread, (git_dir, work_tree), config,
                            config_env_settings)
    # A redirection (`> main`, `2>&1`) is no argument of the subcommand; a quoted word is never one.
    arguments = shell_command.without_redirection_words(argument_words[index + 1:], words[index + 1:])
    return GitCall(argument_words[index].lower(), arguments, config, directory, git_dir, work_tree, placed,
                   context.environment_sets_config)


def is_linked_git_folder(directory, git_dir=None):
    """True when `git -C <directory> [--git-dir <git_dir>]` acts on a linked worktree's git folder: its own folder and
    the common folder differ. Fails closed: a call git cannot answer (no repo, no git, a timeout) reads as a main
    checkout, and a failure to run git is named on stderr."""
    # Not script_utils.git_output: a failure to spawn git is named on stderr, and the gate reads it as a main checkout.
    command = ["git", "-C", directory]
    if git_dir:
        command.append(f"--git-dir={git_dir}")
    command += ["rev-parse", "--absolute-git-dir", "--git-common-dir"]
    try:
        finished = subprocess.run(command, capture_output=True, text=True, timeout=REV_PARSE_TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError) as error:
        sys.stderr.write(f"[git_calls] {' '.join(command)} failed ({error}); reading the call as a main checkout\n")
        return False
    lines = finished.stdout.splitlines()
    if finished.returncode != 0 or len(lines) != 2:
        return False
    git_folder, common_folder = (os.path.realpath(os.path.join(directory, line)) for line in lines)
    return git_folder != common_folder


def is_linked_worktree(call):
    """True when the repo the call acts on is a linked worktree. Git finds the repo from `--git-dir`, else from the
    call's directory. `--work-tree` moves the checkout: when the call names one, its folder must itself be in a linked
    worktree as well. With `--git-dir` and no `--work-tree`, git takes the call's directory as the work tree, so that
    directory must be in a linked worktree too. Fails closed: a call the gate cannot place, and a repo it cannot
    find, read as a main checkout."""
    if not call.placed:
        return False
    if not is_linked_git_folder(call.directory, call.git_dir):
        return False
    if call.work_tree:
        return is_linked_git_folder(call.work_tree)
    if call.git_dir:
        return is_linked_git_folder(call.directory)
    return True


def has_unfollowed_directory_move(code, follows_cds):
    """True when the code may run a call in a folder the gate does not follow: a `cd` it skips (subshell, code
    runner text), a `pushd` or `popd`, a `cd` that runs only on a condition (after `||`, after a left side that is not
    a `cd`, or inside an `if`, `case`, `for`, `select`, `while` or `until` body), or a `cd` behind `builtin`,
    `command`, `{`, `while` or `until`, or a `cd`, `pushd` or `popd` spelled with quotes or escapes (`"cd"`, `\\cd`,
    `builtin "cd"`). Every call in such a command is unplaced."""
    if not follows_cds or PUSHD_OR_POPD.search(code):
        return True
    if has_conditional_cd(code):
        return True
    if shell_command.names_code_runner(code) and CD_WORD_PATTERN.search(code):
        return True
    return has_hidden_directory_move(code)


def has_hidden_directory_move(code):
    """True when a statement runs `cd`, `pushd` or `popd` in a spelling the gate does not follow. The gate follows a
    `cd` only as the plain first word of the blanked statement; the resolved words (quotes and escapes removed), with
    the prefix words dropped, show the command the shell runs."""
    for pair in shell_statements.statement_word_pairs(code):
        head = pair.resolved
        while head and head[0] in DIRECTORY_MOVE_PREFIXES:
            head = head[1:]
        if not head or head[0] not in shell_directory.DIRECTORY_MOVE_WORDS:
            continue
        if pair.blanked[0] != shell_directory.CD_WORD:
            return True
    return False


def has_conditional_cd(code):
    """True when a `cd` may not run: it follows `||` in its list, follows `&&` after a statement that is not a `cd`,
    or sits in an `if`, `case`, `for`, `select`, `while` or `until` body or condition (any `cd` word of a step in
    one counts, a `case` pattern's `)` hides the command after it), or sits after or before `|` or `|&` (a subshell),
    or runs in the background; a step after a `&` counts too (fail closed: the gate does not track which list the
    `&` ended)."""
    steps = shell_command.split_command_steps(shell_statements.shell_code(code))
    block_depth = 0
    previous_is_cd = False
    for index in range(len(steps)):
        reading = read_step(steps, index, block_depth, previous_is_cd)
        if reading.conditional:
            return True
        block_depth = reading.block_depth
        previous_is_cd = reading.previous_is_cd
    return False


class StepReading(NamedTuple):
    conditional: bool
    block_depth: int
    previous_is_cd: bool


def read_step(steps, index, block_depth, previous_is_cd):
    """What one step tells has_conditional_cd: whether it holds a `cd` that may not run, and the block depth and
    previous-step-is-cd state after it."""
    operator, step = steps[index]
    parts = shell_statements.split_on_pipe_both(step)
    next_operator = steps[index + 1][0] if index + 1 < len(steps) else ""
    runs_in_subshell = (len(parts) > 1 or operator in SUBSHELL_OPERATORS or next_operator == "|"
                        or shell_steps.step_runs_in_background(steps, index))
    runs_after_other = operator == "&&" and not previous_is_cd
    may_not_run = (runs_in_subshell or runs_after_other or shell_steps.step_may_be_skipped(steps, index))
    for part in parts:
        reading = read_part(part, block_depth)
        if reading is None:
            continue
        block_depth = reading.block_depth
        if reading.cd_in_block or (reading.is_cd and may_not_run):
            return StepReading(True, block_depth, previous_is_cd)
        previous_is_cd = reading.is_cd
    return StepReading(False, block_depth, previous_is_cd)


class PartReading(NamedTuple):
    block_depth: int
    is_cd: bool
    cd_in_block: bool


def read_part(part, block_depth):
    """What one pipe part of a step tells has_conditional_cd: the block depth after it, whether it runs `cd`, and
    whether a `cd` word sits in an open block. None for a part with no words."""
    words = shell_command.raw_words_without_redirections(part.lstrip(PART_OPENERS))
    words = shell_statements.without_leading_noise(words, kept_words=("if",))
    if not words:
        return None
    block_depth = block_depth_after(block_depth, words[0])
    while words and words[0] in ("if", "!"):
        words = words[1:]
    is_cd = words[:1] == [shell_directory.CD_WORD]
    cd_in_block = block_depth > 0 and shell_directory.CD_WORD in words
    return PartReading(block_depth, is_cd, cd_in_block)


def block_depth_after(block_depth, head):
    """The depth of nested `if`/`case`/loop blocks after a statement that starts with the word `head`."""
    if head in BLOCK_OPENERS:
        return block_depth + 1
    if head in BLOCK_CLOSERS:
        return max(block_depth - 1, 0)
    return block_depth


def quoted_environment_sets(code, names):
    """True when a word before a statement's `git` word, once its quotes are removed, assigns a name in `names`
    (`env "GIT_CONFIG_COUNT=1" git ...`). A statement with no `git` word and the words after `git` do not count, so
    `echo "HOME=x"` and a commit message that names the variable are no assignment."""
    for pair in shell_statements.statement_word_pairs(code):
        git_positions = [index for index, word in enumerate(pair.resolved) if os.path.basename(word) == "git"]
        if not git_positions:
            continue
        for word in pair.resolved[:git_positions[0]]:
            assignment = shell_statements.ASSIGNMENT.match(word)
            if assignment and assignment.group()[:-1] in names:
                return True
    return False


def command_context(code, follows_cds, context):
    """`context` with what the code's own text adds: the placement-moving environment, the config-setting
    environment and the unfollowed directory move."""
    # Searched with quoted text blanked, so a message that names GIT_CONFIG_COUNT= is no assignment.
    unquoted_code = shell_statements.clean(code)
    environment_moves_placement = (context.environment_moves_placement
                                   or PLACEMENT_ENVIRONMENT.search(unquoted_code) is not None
                                   or quoted_environment_sets(code, PLACEMENT_ENVIRONMENT_NAMES))
    environment_sets_config = (context.environment_sets_config
                               or CONFIG_ENVIRONMENT.search(unquoted_code) is not None
                               or quoted_environment_sets(code, CONFIG_ENVIRONMENT_NAMES))
    unfollowed_move = context.unfollowed_move or has_unfollowed_directory_move(code, follows_cds)
    return context._replace(environment_moves_placement=environment_moves_placement,
                            unfollowed_move=unfollowed_move, environment_sets_config=environment_sets_config)


def git_calls(command, directory=".", context=NO_CONTEXT):
    """Every GitCall the command makes in command position, those inside `$(...)` and backticks included. A call
    runs in the directory an earlier `cd` of the command moved to, else in `directory`. In code that names a code
    runner, each `git` word starts a call, quoted or not. `context` holds what the code around the command
    already does; the command's own text adds to it."""
    code = shell_statements.shell_code(command)
    # A `cd` after a `(` may run in a subshell, whose directory does not carry on, so none is followed.
    follows_cds = SUBSHELL_CD.search(code) is None
    context = command_context(code, follows_cds, context)

    def directory_at(offset):
        if not follows_cds:
            return directory
        return resolved_directory(code[:offset], directory)

    if shell_command.names_code_runner(code):
        text_context = context._replace(from_code_text=True)
        text_calls = [git_call(found.group().split(), directory_at(found.start()), text_context)
                      for found in GIT_CALL_TEXT.finditer(code)]
        return [call for call in text_calls if call]

    spans = shell_statements.code_spans(code)
    outer_code = code
    for span_start, span_end, _span in reversed(spans):
        outer_code = outer_code[:span_start] + outer_code[span_end:]

    calls = []
    statement_directory = directory
    for pair in shell_statements.statement_word_pairs(outer_code):
        words = pair.blanked
        if words[0] == "cd":
            if follows_cds:
                statement_directory = cd_directory(words, statement_directory)
            continue
        call = git_call(words, statement_directory, context, resolved_words=pair.resolved)
        if call:
            calls.append(call)

    for span_start, _span_end, span in spans:
        calls += git_calls(span, directory_at(span_start), context)
    return calls


def resolved_directory(code, directory):
    """The directory the `cd` statements of `code` leave a command in, starting from `directory`."""
    for words in shell_statements.statements(code):
        if words[0] == "cd":
            directory = cd_directory(words, directory)
    return directory


def cd_directory(words, directory):
    """The directory the `cd` statement `words` moves to from `directory`: `cd -L|-P|-e|-@|-- <dir>` follows `<dir>`,
    a bare `cd` goes home and `cd -` goes to OLDPWD, which is not known, so the call reads as unplaced."""
    arguments = words[1:]
    while arguments and arguments[0] in CD_OPTIONS:
        arguments = arguments[1:]
    if not arguments:
        return joined_directory(directory, os.path.expanduser("~"))
    if arguments[0] == "-":
        return os.path.join(directory, UNREAD_DIRECTORY)
    return joined_directory(directory, arguments[0])
