"""Read a shell command line as steps joined by operators, without running or fully parsing it."""
import os
import posixpath
import re
import shlex

SETUP_STEP = re.compile(r"^[ \t(]*(cd[ \t]|source[ \t]|\.[ \t]|export[ \t]|([^\W\d]\w*=[^ \t]*[ \t]*)+$)")
# `>|` (clobber redirection) is not a pipe. `|&` (pipe both streams), `>&`, `&>` and `&&` are not a lone `&`; a lone
# `&` sends the step before it to the background.
OPERATOR = re.compile(r"(\|\||&&|(?<!>)\|(?!&)|(?<![>&|])&(?![&>])|;|\n)")
LINE_CONTINUATION = re.compile(r"\\\r?\n")
LEADING_BRACES = re.compile(r"(?:[ \t]*\{(?=[ \t]))*")
TRAILING_BRACES = re.compile(r"(?:(?:^|[ \t])\}[ \t]*)+$")
SEPARATOR_CHARS = set("();|&\n")
REDIRECT_CHARS = set("<>&")
# shlex drops the quotes and escapes, so a quoted or escaped operator character would read as a real operator.
HIDDEN_OPERATOR = re.compile(r"""\\[();|&<>\n]|(["'])\s*[();|&<>\n][\s();|&<>]*\1""")
# `5 >f` redirects stdout and leaves 5 as an argument, but dropping a redirect's file descriptor would take the 5.
SPACED_REDIRECT_NUMBER = re.compile(r"(?<!\S)\d+[ \t]+[<>]")
# The target of `>&1`, `2>&1` or `>&-` copies or closes a file descriptor; any other `>&` target is a file.
FILE_DESCRIPTOR_TARGET = re.compile(r"\d+-?|-")
# docker and docker compose options that take the next word as their value. `--opt=value` is one word, read as a flag.
DOCKER_VALUE_OPTIONS = {
    "-e", "--env", "-w", "--workdir", "-u", "--user", "--entrypoint", "-v", "--volume", "--name", "-p", "--publish",
    "--network", "--env-file", "-f", "--file", "--project-name", "--project-directory", "--profile", "-l", "--label",
    "--mount", "--add-host", "--cap-add", "--cap-drop", "--hostname", "--platform", "--context", "--volumes-from",
    "-m", "--memory", "--cpus", "--gpus", "--shm-size", "--ulimit", "--tmpfs", "--device", "--restart", "--pull",
    "--security-opt", "--log-opt", "--index", "--ansi", "--progress",
}
GROUP_WORDS = {"{", "!", "if", "then", "elif", "else", "while", "until", "do"}
SHELL_INTERPRETERS = {"sh", "bash", "zsh", "dash", "ksh"}
# A command text that names one of these as a word may run code the parser does not read: a shell's `-c` text, an
# `eval` argument, a command run through another program or on another host. A quoted mention counts, except a
# shell name right after a `|` or a backslash: that is a regex alternative such as `(py|sh)`.
CODE_RUNNERS = re.compile(
    r"(?<![|\\])\b(" + "|".join(sorted(SHELL_INTERPRETERS)) + r")(?![\w.-])"
    r"|\b(eval|su|script|flock|watch|xargs|ssh|parallel)\b"
    r"|\bgit\b[^\n]*\brebase\b[^\n]*\s(--exec|-x)\b"
    r"|\bfind\b[^\n]*\s-exec(dir)?\b"
    r"|\b(docker|podman)\b[^\n]*\b(exec|run)\b"
    r"|\bkubectl\b[^\n]*\bexec\b"
)
SHELL_VALUE_OPTIONS = {"--rcfile", "--init-file", "--init"}
# Words that run the command after them; each maps to the options that take the next word as their value.
WRAPPER_VALUE_OPTIONS = {
    "env": {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"},
    "sudo": {"-u", "--user", "-g", "--group", "-h", "--host", "-p", "--prompt", "-C", "-r", "-t", "-U", "-D", "-R",
             "--chdir", "--chroot"},
    "doas": {"-u", "-C"},
    "timeout": {"-s", "--signal", "-k", "--kill-after"},
    "nice": {"-n", "--adjustment"},
    "nohup": set(),
    "time": {"-o", "--output", "-f", "--format"},
    "command": set(),
    "exec": {"-a"},
    "builtin": set(),
    "stdbuf": {"-i", "-o", "-e"},
    "setsid": set(),
    "detach": set(),
    "ionice": {"-c", "-n", "-p"},
    "unbuffer": set(),
    "taskset": set(),
}
# The wrappers whose first word after their options is a value, not the command: timeout's duration, taskset's CPU
# mask or list.
WRAPPERS_WITH_A_LEADING_VALUE = {"timeout", "taskset"}
# `uv run`, `poetry run` and `pipenv run` run the command after their options.
RUNNER_WRAPPERS = {
    "uv": {"--with", "--with-requirements", "--python", "-p", "--directory", "--project", "--env-file", "--group",
           "--extra", "--package", "--index"},
    "poetry": {"-C", "--directory", "-P", "--project"},
    "pipenv": {"--python", "--pypi-mirror"},
}
# By interpreter family: the name pattern, the flags after which it runs no program from stdin or a script (a module,
# a version, help), the options that take the next word as their value, the letters that end a short-flag cluster
# whose next word is code (`-c`, `-Bc`, `-le`), and the long flags that take the next word as code. nodejs is the
# node family.
INTERPRETER_FAMILIES = {
    "python": {"name": r"python[\d.]*", "no_stdin_code_flags": {"-m", "-V", "-VV", "--version", "-h", "--help"},
               "value_options": {"-W", "-X", "-Q"}, "inline_code_letters": "c", "inline_code_flags": set()},
    "perl": {"name": r"perl", "no_stdin_code_flags": {"-v", "-V", "--version", "-h", "--help"},
             "value_options": {"-I", "-M", "-C"}, "inline_code_letters": "eE", "inline_code_flags": set()},
    "ruby": {"name": r"ruby", "no_stdin_code_flags": {"-v", "--version", "-h", "--help"},
             "value_options": {"-I", "-r", "-C", "-E"}, "inline_code_letters": "e", "inline_code_flags": set()},
    "node": {"name": r"node(?:js)?", "no_stdin_code_flags": {"-v", "--version", "-h", "--help"},
             "value_options": {"-r", "--require", "--import", "-C", "--conditions"}, "inline_code_letters": "ep",
             "inline_code_flags": {"--print", "--eval"}},
    "php": {"name": r"php", "no_stdin_code_flags": {"-v", "--version", "-h", "--help"},
            "value_options": {"-d", "-c", "-r"}, "inline_code_letters": "r", "inline_code_flags": set()},
}
INTERPRETER = re.compile("|".join(family["name"] for family in INTERPRETER_FAMILIES.values()), re.I)
MANAGE_SCRIPT = "manage.py"
# Words that name stdin as the program file of an interpreter, like `-`.
STDIN_PROGRAM_FILES = {"-", "/dev/stdin", "/dev/fd/0", "/proc/self/fd/0"}
# Redirections that carry code inside the command: a heredoc or a here-string. A file read with `<` is a script file,
# as in `python3 <file>`.
STDIN_CODE_REDIRECTIONS = {"<<", "<<<"}


def interpreter_family(word):
    # The INTERPRETER_FAMILIES key whose name fully matches the basename of word (/usr/bin/python3.12, nodejs), or None.
    program = os.path.basename(word)
    for family, rules in INTERPRETER_FAMILIES.items():
        if re.fullmatch(rules["name"], program, re.I):
            return family
    return None


def reads_code_from_stdin(words, redirections, piped):
    """True when the simple command runs a bare interpreter whose program text arrives on stdin: `python3 -`, a
    heredoc or here-string into it, or a pipe into it. An interpreter given a script file (also by `<`), `-m` or a
    version flag reads stdin as data, not as code. `manage.py shell` is a bare interpreter: it runs stdin as code."""
    words = command_after_wrappers(words)
    if not words:
        return False

    if os.path.basename(words[0]) == MANAGE_SCRIPT:
        words = ["python", *words]
    if not INTERPRETER.fullmatch(os.path.basename(words[0])):
        return False

    family = interpreter_family(words[0])
    value_options = INTERPRETER_FAMILIES[family]["value_options"]
    no_stdin_code_flags = INTERPRETER_FAMILIES[family]["no_stdin_code_flags"]
    index = 1
    while index < len(words):
        word = words[index]
        if word in STDIN_PROGRAM_FILES:
            return True
        if os.path.basename(word) == MANAGE_SCRIPT and words[index + 1:index + 2] == ["shell"]:
            break
        if family == "python" and word.startswith("-m") and len(word) > 2:
            return False
        if word in no_stdin_code_flags or not word.startswith("-"):
            return False
        if word in value_options and words[index + 1:index + 2] and words[index + 1] in STDIN_PROGRAM_FILES:
            return True
        index += 2 if word in value_options else 1

    has_stdin_code = any(operator in STDIN_CODE_REDIRECTIONS for operator, _target in redirections)
    return piped or has_stdin_code


def redirection_writes_file(operator, target):
    """True when a redirection can create or change a file: an output operator (`>`, `>>`, `&>`, `>&`, `<>`) whose
    target is not /dev/null and not a file-descriptor copy (`>&1`, `>&2`, `>&-`). An input redirection never does."""
    if ">" not in operator or target == "/dev/null":
        return False
    return not (operator.endswith("&") and FILE_DESCRIPTOR_TARGET.fullmatch(target))


def split_simple_commands(command):
    """The words of each simple command in a shell command, with the quotes and escapes resolved (see
    parse_simple_commands). A command that is only a redirection is left out."""
    return [words for words, _redirections in parse_simple_commands(command) if words]


def parse_simple_commands(command):
    """Split a shell command into its simple commands, each a pair (words, redirections). Words have the quotes and
    escapes resolved; a redirection is (operator, target), with a target of "" when none follows. Operators, `(`,
    `)` and an unquoted newline end a command (an empty one is left out); a redirection's file descriptor number is
    not a word; a comment is not a comment, its words stay. Raises ValueError for text this reading cannot trust: an
    unclosed quote, a quoted or escaped operator character, a number then a space then a redirection (`5 >f`), or a
    run of operator characters it cannot sort (`<|`). `>|` is an output redirection."""
    return [(words, redirections) for words, redirections, _piped in parse_piped_commands(command)]


def parse_piped_commands(command):
    """Like parse_simple_commands, but each command is a triple (words, redirections, piped): piped is True when
    the command reads from a pipe, that is, a `|` or `|&` comes right before it. Raises ValueError as
    parse_simple_commands does."""
    if HIDDEN_OPERATOR.search(command):
        raise ValueError("operator character inside quotes or after a backslash")
    if SPACED_REDIRECT_NUMBER.search(command):
        raise ValueError("a number, a space and a redirection")

    lexer = shlex.shlex(command, posix=True, punctuation_chars="();<>|&\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    reader = _PipedCommandReader()
    for token in lexer:
        reader.read(token)
    return reader.finish()


class _PipedCommandReader:
    """The commands read so far from the tokens of parse_piped_commands, and the command being read."""

    def __init__(self):
        self.commands = []
        self.piped = False
        self.next_piped = False
        self.words = []
        self.redirections = []
        self.pending_operator = None

    def read(self, token):
        characters = set(token)
        if token and characters <= SEPARATOR_CHARS:
            self._end_command(token)
        elif token and (characters <= REDIRECT_CHARS or token == ">|"):
            self._start_redirection(token)
        elif token and characters <= SEPARATOR_CHARS | REDIRECT_CHARS:
            raise ValueError("unsorted operator characters: " + token)
        elif self.pending_operator is not None:
            self.redirections.append((self.pending_operator, token))
            self.pending_operator = None
        else:
            self.words.append(token)

    def finish(self):
        self._close_pending_operator()
        self._save_command()
        return self.commands

    def _close_pending_operator(self):
        if self.pending_operator is not None:
            self.redirections.append((self.pending_operator, ""))
        self.pending_operator = None

    def _save_command(self):
        if self.words or self.redirections:
            self.commands.append((self.words, self.redirections, self.piped))

    def _end_command(self, separator):
        self._close_pending_operator()
        if self.words or self.redirections:
            self._save_command()
            self.next_piped = False
        if separator.replace("\n", "").replace("(", "") in ("|", "|&"):
            self.next_piped = True
        self.piped = self.next_piped
        self.words = []
        self.redirections = []

    def _start_redirection(self, operator):
        self._close_pending_operator()
        if self.words and self.words[-1].isdigit():
            self.words.pop()
        self.pending_operator = operator


def unwrap_docker(words):
    """The command that a `docker compose exec|run`, `docker-compose exec|run`, `docker exec|run` or `docker
    container exec|run` call runs inside its container, as a list of words (empty when it names none). None when the
    words are not such a call. An option that takes a value is skipped with its value; any other option is a flag."""
    command_start = docker_command_start(words)
    if command_start is None:
        return None
    return words[command_start:]


def docker_command_start(words):
    # The index in words where the command run inside the container starts, or None when the words are not a docker
    # exec or run call.
    if not words or words[0] not in ("docker", "docker-compose"):
        return None

    index = skip_options(words, 1, DOCKER_VALUE_OPTIONS)
    if words[0] == "docker" and index < len(words) and words[index] in ("compose", "container"):
        index = skip_options(words, index + 1, DOCKER_VALUE_OPTIONS)
    if index >= len(words) or words[index] not in ("exec", "run"):
        return None

    # The word after the options is the service, container or image; the rest is the command.
    index = skip_options(words, index + 1, DOCKER_VALUE_OPTIONS)
    return min(index + 1, len(words))


def docker_forwarded_variables(words):
    """The names of the host variables that a docker exec or run call passes into the container with `-e NAME`,
    `--env NAME`, `--env=NAME` or `-eNAME` (an option that sets a value, `-e NAME=value`, forwards none). An empty
    set when the words are not such a call."""
    return {value for value in docker_environment_values(words) if "=" not in value}


def docker_set_variables(words):
    """The names of the variables that a docker exec or run call sets inside the container with `-e NAME=value`,
    `--env NAME=value`, `--env=NAME=value` or `-eNAME=value`. An empty set when the words are not such a call."""
    return {value.split("=", 1)[0] for value in docker_environment_values(words) if "=" in value}


def docker_environment_values(words):
    # The value of each -e or --env option of a docker exec or run call: `NAME` or `NAME=value`.
    command_start = docker_command_start(words)
    if command_start is None:
        return []

    values = []
    index = 1
    while index < command_start:
        word = words[index]
        index += 1
        value = None
        if word in ("-e", "--env"):
            value = words[index] if index < command_start else None
            index += 1
        else:
            value = _attached_environment_value(word)
        if value is None and word in DOCKER_VALUE_OPTIONS:
            index += 1
        if value:
            values.append(value)
    return values


def _attached_environment_value(word):
    # The value in `--env=NAME` or `-eNAME`, or None when the word is neither.
    if word.startswith("--env="):
        return word[len("--env="):]
    if word.startswith("-e") and not word.startswith("--"):
        return word[2:]
    return None


def skip_options(words, index, value_options):
    # The index of the first word from index on that is no option: an option that takes a value is skipped with it.
    while index < len(words) and words[index].startswith("-"):
        index += 2 if words[index] in value_options else 1
    return index


# git's own options that take the next word as their value.
GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--super-prefix",
                     "--attr-source"}


def git_options(words):
    """The (option, value) pairs of git's own options in the words of a git call, and the index of the first word
    after them; a flag's value is None."""
    options = []
    index = 1
    while index < len(words) and words[index].startswith("-"):
        option = words[index]
        takes_value = option in GIT_VALUE_OPTIONS and index + 1 < len(words)
        options.append((option, words[index + 1] if takes_value else None))
        index += 2 if takes_value else 1
    return options, index


def is_git_word(word):
    """True when the word's base name is `git`, so a path to git counts."""
    return posixpath.basename(word) == "git"


def git_subcommand(words):
    """The subcommand of the git call in the words, after git's own options; None when it names none."""
    _options, index = git_options(words)
    if index == len(words):
        return None
    return words[index]


def without_assignments(words):
    """The words with the leading NAME=value words dropped."""
    while words and "=" in words[0] and not words[0].startswith("-"):
        words = words[1:]
    return words


def without_flag_values(words, value_flags):
    # The words with the value word after each of value_flags dropped. The flag itself stays.
    kept_words = []
    skip_value = False
    for word in words:
        if skip_value:
            skip_value = False
            continue
        skip_value = word in value_flags
        kept_words.append(word)
    return kept_words


def contains_word_run(words, run):
    # True when the words hold the words of run next to each other, in order, anywhere in the list.
    return any(words[start:start + len(run)] == run for start in range(len(words) - len(run) + 1))


def command_after_wrappers(words, peel_containers=True):
    """The words of the command that a simple command finally runs, with the wrapper words, their flags and their
    values dropped: each WRAPPER_VALUE_OPTIONS word (env, sudo, timeout, setsid, detach, ...) with its flags and
    values (but not `command -v`/`-V`, which is the command itself), NAME=value assignments, uv/poetry/pipenv run,
    a leading group word (GROUP_WORDS) and, unless peel_containers is False, a docker exec or run call. Words that
    name no wrapper come back as they are; an empty list when the wrappers name no command."""
    word_lists = list(_peeled_word_lists(words, peel_containers))
    return word_lists[-1]


def wrapper_chain(words):
    """The basename of each wrapper word that command_after_wrappers drops, in order, then the basename of the final
    command word. Empty only when the words are empty or only NAME=value assignments; words that are only wrappers
    give just the wrapper names."""
    return [os.path.basename(step[0]) for step in _peeled_word_lists(words) if step]


def _peeled_word_lists(words, peel_containers=True):
    # Each word list on the way through the wrappers, assignments dropped: first the whole command, then the words
    # after each peeled wrapper, last the command the wrappers run. Only the last one can be empty: the wrappers
    # named no command.
    while True:
        words = without_assignments(words)
        yield words
        if not words:
            return

        peeled = _peel_wrapper_once(words, peel_containers)
        if peeled is None:
            return
        words = peeled


def _peel_wrapper_once(words, peel_containers):
    # The words after the one wrapper that words starts with, or None when it starts with no wrapper to peel.
    name = os.path.basename(words[0])
    container_command = unwrap_docker(words) if peel_containers else None
    if container_command is not None:
        return container_command
    if words[0] in GROUP_WORDS:
        return words[1:]
    if name in RUNNER_WRAPPERS:
        return _peel_runner_wrapper(words, name)
    if name in WRAPPER_VALUE_OPTIONS:
        return _peel_option_wrapper(words, name)
    return None


def _peel_runner_wrapper(words, name):
    # The words after `uv run`, `poetry run` or `pipenv run` and its options, or None for any other subcommand.
    if len(words) < 2 or words[1] != "run":
        return None
    command_start = skip_options(words, 2, RUNNER_WRAPPERS[name])
    return words[command_start:]


def _peel_option_wrapper(words, name):
    # The words after a WRAPPER_VALUE_OPTIONS wrapper, its options and its leading value; None for `command -v`.
    if name == "command" and words[1:2] in (["-v"], ["-V"]):
        return None
    rest = words[skip_options(words, 1, WRAPPER_VALUE_OPTIONS[name]):]
    if name in WRAPPERS_WITH_A_LEADING_VALUE:
        return rest[1:]
    return rest


def peeled_commands(simple_commands):
    # The words of each simple command with its wrappers peeled; a command that is only wrappers is dropped.
    unwrapped = (command_after_wrappers(words) for words in simple_commands)
    return [words for words in unwrapped if words]


def resolved_command_words(command):
    """The words of each simple command, quotes and escapes resolved and wrapper words (`builtin`, `command`, `{`)
    dropped; empty when shlex cannot read the command."""
    try:
        simple_commands = split_simple_commands(LINE_CONTINUATION.sub("", command))
    except ValueError:
        return []
    return peeled_commands(simple_commands)


def step_words(command):
    """The words of each step of the command with its wrappers peeled (env, nice, timeout, uv run, a docker exec).
    Text shlex cannot read is cut on its operators and split on whitespace, so a step is still read."""
    try:
        simple_commands = split_simple_commands(command)
    except ValueError:
        simple_commands = [segment_words(step) for _operator, step in split_command_steps(command)]
    return peeled_commands(simple_commands)


def segment_words(segment):
    """The words of one command text, quotes removed: shlex.split reads back what shlex.join wrote, so quoted inline
    code stays one word. Text shlex cannot read (an unbalanced quote) is split on whitespace."""
    try:
        return shlex.split(segment)
    except ValueError:
        return [word for word in re.split(r"[ \t\n]+", segment) if word]


def names_code_runner(command):
    """True when the command text names a code runner (CODE_RUNNERS) as a word."""
    return bool(CODE_RUNNERS.search(command))


def runs_shell(words):
    """True when the simple command, once its wrapper words are dropped, runs a shell interpreter."""
    words = command_after_wrappers(words)
    return bool(words) and os.path.basename(words[0]).lower() in SHELL_INTERPRETERS


def shell_code_argument(words):
    """The code text a shell interpreter runs from its `-c` option (`-c`, `-lc`, `-x -c`), once wrapper words are
    dropped; None when the words run no shell or give it no `-c` code."""
    words = command_after_wrappers(words)
    if not words or os.path.basename(words[0]).lower() not in SHELL_INTERPRETERS:
        return None

    index = 1
    while index < len(words) and words[index].startswith(("-", "+")):
        word = words[index]
        if word.startswith("-") and not word.startswith("--") and "c" in word[1:]:
            return _code_after_option(words, index)
        # An option takes the next word as its value: a long option named in SHELL_VALUE_OPTIONS, or a short-option
        # cluster ending in `o` or `O` (`-o`, `+o`, `-euo`).
        takes_value = word in SHELL_VALUE_OPTIONS or (not word.startswith("--") and word[-1] in "oO")
        index += 2 if takes_value else 1
    return None


def _code_after_option(words, index):
    # The `-c` code text in the word after the option at index, or None when the option is last.
    if index + 1 >= len(words):
        return None
    # The shell removes a backslash before `$` or a backtick inside double quotes; shlex keeps it.
    return re.sub(r"\\([$`])", r"\1", words[index + 1])


def split_command_steps(command):
    """Split a shell command on ||, &&, | ; newline and a lone & into (operator, step) pairs. The operator is the one
    that comes before the step; the first step has "". A newline counts as ";". An operator inside single or double
    quotes, or after a backslash, stays in its step."""
    quoted = quoted_positions(command)
    steps = []
    operator = ""
    step_start = 0
    for match in OPERATOR.finditer(command):
        if match.start() in quoted:
            continue
        steps.append((operator, command[step_start:match.start()]))
        operator = ";" if match.group() == "\n" else match.group()
        step_start = match.end()
    steps.append((operator, command[step_start:]))
    return steps


def and_steps(command):
    """The stripped steps of a command joined only by &&, or None when it joins its steps with any other operator."""
    steps = split_command_steps(command)
    if any(operator not in ("", "&&") for operator, _step in steps):
        return None
    return [step.strip() for _operator, step in steps]


def and_steps_or_whole(command):
    """The stripped && steps of a command, or the stripped command as the one step when it joins its steps with any
    other operator."""
    return and_steps(command) or [command.strip()]


def quoted_positions(command, unclosed_is_quoted=True):
    # The indexes of the characters that sit inside quotes, inside a comment (after its `#`, up to the newline) or
    # right after a backslash outside single quotes. A quote that never closes covers the rest of the command, unless
    # unclosed_is_quoted is False: then the text after it counts as unquoted, as a check that must not be hidden by a
    # stray quote needs. A quote character inside a comment opens no quote. The text of a `$(...)` or backtick span
    # inside double quotes is code the shell runs, so it is not quoted: it is read with its own quote state.
    scan = _QuoteScan(command)
    scan.run()
    positions = scan.positions
    if scan.levels[0]["quote"] is not None and not unclosed_is_quoted:
        positions = {position for position in positions if position < scan.quote_opened_at}
    return positions


class _QuoteScan:
    """The state of one quoted_positions pass over a command, one character at a time."""

    def __init__(self, command):
        self.command = command
        self.positions = set()
        # One level per open `"$(` or "`" span, after the base level: its quote, how it closes, and its open `(` count.
        self.levels = [{"quote": None, "closer": None, "depth": 0}]
        self.quote_opened_at = 0
        self.index = 0

    def run(self):
        while self.index < len(self.command):
            character = self.command[self.index]
            level = self.levels[-1]
            if level["quote"] is None:
                self._read_unquoted(character, level)
            else:
                self._read_quoted(character, level)
            self.index += 1

    def _read_unquoted(self, character, level):
        if character in "'\"":
            self._open_quote(character, level)
        elif character == "\\":
            self._hide_next_character()
        elif character == "#" and self._starts_comment():
            self._hide_comment()
        else:
            self._read_span_syntax(character, level)

    def _read_span_syntax(self, character, level):
        # Track the parentheses of an open `$(` span and the character that closes the span.
        if character == "(" and level["closer"] == ")":
            level["depth"] += 1
        elif character == ")" and level["closer"] == ")" and level["depth"]:
            level["depth"] -= 1
        elif character == level["closer"]:
            self.levels.pop()

    def _read_quoted(self, character, level):
        quote = level["quote"]
        if character == quote:
            level["quote"] = None
        elif character == "\\" and quote == '"':
            self._hide_next_character()
        elif quote == '"' and self.command.startswith("$(", self.index):
            self.levels.append({"quote": None, "closer": ")", "depth": 0})
            self.index += 1
        elif quote == '"' and character == "`":
            self.levels.append({"quote": None, "closer": "`", "depth": 0})
        else:
            self.positions.add(self.index)

    def _open_quote(self, character, level):
        level["quote"] = character
        if len(self.levels) == 1:
            self.quote_opened_at = self.index

    def _hide_next_character(self):
        self.positions.add(self.index + 1)
        self.index += 1

    def _starts_comment(self):
        return self.index == 0 or self.command[self.index - 1] in " \t\r\f\v\n;&|()"

    def _hide_comment(self):
        comment_end = self.command.find("\n", self.index)
        if comment_end == -1:
            comment_end = len(self.command)
        self.positions.update(range(self.index + 1, comment_end))
        # run() adds one after each character, so stop on the newline's predecessor.
        self.index = comment_end - 1


def unquoted_matches(pattern, text, extra_hidden=()):
    """The matches of the compiled pattern in text whose start is not inside quotes, nor at a position in
    extra_hidden. A quote that never closes hides nothing."""
    hidden = quoted_positions(text, unclosed_is_quoted=False)
    hidden.update(extra_hidden)
    return [match for match in pattern.finditer(text) if match.start() not in hidden]


def substitution_spans(text):
    """The text inside each outermost `$(...)` and backtick pair in text that is not in single quotes, a comment or
    after a backslash; one inside double quotes counts. A span that never closes runs to the end of the text."""
    hidden = quoted_positions(text, unclosed_is_quoted=False)
    spans = []
    index = 0
    while index < len(text):
        if index in hidden:
            index += 1
            continue

        if text.startswith("$(", index):
            end = _parenthesis_span_end(text, index, hidden)
            spans.append(text[index + 2:end])
            index = end
        elif text[index] == "`":
            end = _backtick_span_end(text, index)
            spans.append(text[index + 1:end])
            index = end
        index += 1
    return spans


PARENTHESIS_DEPTH_CHANGE = {"(": 1, ")": -1}


def _parenthesis_span_end(text, start, hidden):
    # The index of the `)` that closes the `$(` at start, or the end of the text when it never closes.
    depth = 0
    for position in range(start + 1, len(text)):
        change = 0 if position in hidden else PARENTHESIS_DEPTH_CHANGE.get(text[position], 0)
        depth += change
        if depth == 0:
            return position
    return len(text)


def _backtick_span_end(text, start):
    # The index of the backtick that closes the one at start, or the end of the text when it never closes.
    end = text.find("`", start + 1)
    if end == -1:
        return len(text)
    return end


def path_word(word):
    """The path a shell word names: a quote left at either end is dropped and a leading `~` or `~user` is replaced by
    that home directory. A `~user` that names no user stays as it is."""
    for quote in ('"', "'"):
        if word.endswith(quote):
            word = word[:-1]
        if word.startswith(quote):
            word = word[1:]
    return os.path.expanduser(word)


def path_word_is_absolute(raw):
    """True when the path a shell word names (see path_word) starts with `/`, outer blanks ignored."""
    return path_word(raw.strip(" \t\n\r\f\v")).startswith("/")


CD_OPTION = re.compile(r"-[LPe@]+|--")
# A folder word the shell expands or looks up: a parameter, a substitution, a glob or brace, or `~user`.
UNREAD_FOLDER = re.compile(r"[$`*?\[{]|^~[^/]")
# A directory-stack index (`pushd +1`, `cd -1`), not a folder name.
STACK_INDEX = re.compile(r"[+-]\d+")


def cd_folder(words):
    """The folder a `cd` or `pushd` call names (`~` for a bare `cd`), or None for a `popd`, a bare `pushd`, `cd -`,
    zsh's two-word `cd old new`, a directory-stack index, or a folder the shell expands."""
    arguments = [word for word in words[1:] if not CD_OPTION.fullmatch(word)]
    if words[0] == "popd" or len(arguments) > 1:
        return None
    if not arguments:
        return "~" if words[0] == "cd" else None

    folder = arguments[0]
    if folder == "-" or STACK_INDEX.fullmatch(folder) or UNREAD_FOLDER.search(folder):
        return None
    return folder


def step_parts(step):
    """(core, tail) of a step: the command text after the `(` groups it opens, up to the first `)` that closes no `(`
    of its own, and the text after the last such `)` (a redirection or pipe that applies to the closed group). A
    quoted parenthesis is part of the command."""
    quoted = quoted_positions(step, unclosed_is_quoted=False)
    start = 0
    while start < len(step) and step[start] in " \t({" and start not in quoted:
        start += 1
    depth = 0
    closing = []
    for index in range(start, len(step)):
        if index in quoted:
            continue
        if step[index] == "(":
            depth += 1
            continue
        if step[index] != ")":
            continue
        if depth:
            depth -= 1
            continue
        closing.append(index)
    if not closing:
        return step[start:], ""
    return step[start:closing[0]], step[closing[-1] + 1:]


def group_depth_change(step):
    """How many `( ... )` and `{ ...; }` groups the step text opens, minus how many it closes."""
    change = step.count("(") - step.count(")")
    change += LEADING_BRACES.match(step).group().count("{")
    trailing = TRAILING_BRACES.search(step)
    return change - (trailing.group().count("}") if trailing else 0)


def step_may_be_skipped(steps, index):
    """True when an `||` before the step, in the same list (after the last `;`, newline or `&`), can skip it."""
    for position in range(index, 0, -1):
        operator = steps[position][0]
        if operator in (";", "&"):
            return False
        if operator == "||":
            return True
    return False


def runs_only_after_success(steps, earlier, later):
    """True when the step at `later` comes after the step at `earlier`, which itself is not skipped by an `||`, and
    runs only if `earlier` succeeded. The step right after `earlier` must be joined by `&&`; after that `&&` and `|`
    keep the chain (a pipe binds tighter than `&&`). A `;`, newline, `||` or `&` ends it, except inside a `( )` or
    `{ }` group that the chain entered. Limit: a group closed and another one opened in one step is not tracked."""
    if later <= earlier or step_may_be_skipped(steps, earlier):
        return False
    depth = 0
    for position in range(earlier + 1, later + 1):
        operator = steps[position][0]
        if position == earlier + 1 and operator != "&&":
            return False
        if depth == 0 and operator not in ("&&", "|"):
            return False
        depth = max(0, depth + group_depth_change(steps[position][1]))
    return True


def step_runs_in_background(steps, index):
    """True when the `&&`/`||`/`|` list holding the step at `index` is ended by a lone `&`: bash runs that whole
    list in the background."""
    for position in range(index + 1, len(steps)):
        operator = steps[position][0]
        if operator not in ("|", "&&", "||"):
            return operator == "&"
    return False


def step_surely_ran(steps, index, succeeded):
    """True when the step at `index` must have run, given only whether the whole command succeeded. After a
    success every `&&` step ran, but a step behind `||` may have been skipped. After a failure the command stopped
    somewhere unknown, so a step behind `&&` or `||` may never have started, unless every step before that
    operator only sets up the shell (cd, source, export, a bare assignment), which is taken to succeed. A step sent
    to the background with `&` never counts: the command's result says nothing about it."""
    if step_runs_in_background(steps, index):
        return False
    skipping = ("||",) if succeeded else ("&&", "||")
    for position in range(index + 1):
        operator = steps[position][0]
        if operator not in skipping:
            continue
        if succeeded or not SETUP_STEP.match(steps[position - 1][1]):
            return False
    return True
