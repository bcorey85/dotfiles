"""Read a shell command line as steps joined by operators, without running or fully parsing it."""
import itertools
import os
import posixpath
import re
import shlex
from typing import NamedTuple

from code_text import SP
from shell_directory import path_word
from shell_quoting import join_line_continuations, quoted_positions, strip_comments, unquoted_matches

# `>|` and `>&|` (clobber redirection) are not a pipe. `|&` (pipe both streams), `>&`, `&>` and `&&` are not a lone `&`;
# a lone `&` sends the step before it to the background. `<&` (duplicate an input descriptor) is no lone `&` either.
# The group does not capture, so a pattern built on this one keeps its own groups.
OPERATOR = re.compile(r"(?:\|\||&&|(?<!>)(?<!>&)\|(?!&)|(?<![<>&|])&(?![&>])|;|\n)")
# The operators after which a newline continues the list: the next line is the right side of the operator.
LINE_CONTINUING_OPERATORS = ("&&", "||", "|")
SEPARATOR_CHARS = set("();|&\n")
REDIRECT_CHARS = set("<>&")
# shlex drops the quotes and escapes, so a quoted or escaped operator character would read as a real operator.
HIDDEN_OPERATOR = re.compile(r"""\\[();|&<>\n]|(["'])\s*[();|&<>\n][\s();|&<>]*\1""")
# `5 >f` redirects stdout and leaves 5 as an argument, but dropping a redirect's file descriptor would take the 5.
SPACED_REDIRECT_NUMBER = re.compile(r"(?<!\S)\d+[ \t]+[<>]")
# The target of `>&1`, `2>&1` or `>&-` copies or closes a file descriptor; any other `>&` target is a file.
FILE_DESCRIPTOR_TARGET = re.compile(r"\d+-?|-")
# A word that starts a redirect: `>f`, `<f`, `2>f`, `&>f`.
REDIRECT_WORD = re.compile(r"(?:\d+|&)?[<>]")
# Where a redirect target word ends, and the `>` operators that open one: the one copy of both.
WORD_END_CHARACTERS = SP + "|&;<>()"
_REDIRECT_BASE = r">>?&?"
REDIRECT_OPERATOR = _REDIRECT_BASE + "[|!]?"
ADJACENT_BANG_CLOBBER = re.compile(_REDIRECT_BASE + "!")
# The lexer reads `>|`, `>>|`, `&>|`, `>&|` and `>>&|` as one operator token.
CLOBBER_TOKEN = re.compile(r"(?:&?>>?|>>?&)\|")
# A bare redirect word (`>`, `2>`, `&>>`) takes the next word as its target; `2>&1` and `>out` carry theirs.
BARE_REDIRECT_WORD = re.compile(r"^(\d*(?:[<>]{1,2}|>>?[|!])&?|\d*>>?&[|!]|&>{1,2}[|!]?)$")
# docker, podman and docker compose options that take the next word as their value.
# `--opt=value` is one word, read as a flag.
DOCKER_VALUE_OPTIONS = {
    "-e", "--env", "-w", "--workdir", "-u", "--user", "--entrypoint", "-v", "--volume", "--name", "-p", "--publish",
    "--network", "--env-file", "-f", "--file", "--project-name", "--project-directory", "--profile", "-l", "--label",
    "--mount", "--add-host", "--cap-add", "--cap-drop", "--hostname", "--platform", "--context", "--volumes-from",
    "-m", "--memory", "--cpus", "--gpus", "--shm-size", "--ulimit", "--tmpfs", "--device", "--restart", "--pull",
    "--security-opt", "--log-opt", "--index", "--ansi", "--progress",
    "--log-driver", "--cidfile", "--ipc", "--pid", "--cgroupns", "--systemd", "--stop-signal", "--detach-keys",
    "--net", "--pod", "--userns", "--uts", "--cgroup-parent", "--dns", "--dns-search", "--dns-option", "--group-add",
    "--health-cmd", "--health-interval", "--health-retries", "--health-timeout", "--stop-timeout", "--ip", "--ip6",
    "--mac-address", "--label-file", "--pids-limit", "--memory-swap", "--cpu-shares", "--cpuset-cpus",
    "--blkio-weight", "--runtime", "--sysctl", "--storage-opt", "--volume-driver", "--domainname", "--expose",
    "--link", "--network-alias", "--isolation", "--kernel-memory", "--oom-score-adj", "--attach", "-a",
    "-H", "--host", "-c", "--config", "--log-level", "--tlscacert", "--tlscert", "--tlskey", "--connection", "--url",
    "--identity", "--root", "--runroot", "--storage-driver",
    "-h", "--memory-reservation", "--cpu-period", "--cpu-quota", "--cpuset-mems", "--device-cgroup-rule",
    "--device-read-bps", "--device-write-bps", "--annotation", "--tz", "--secret",
}
GROUP_WORDS = {"{", "!", "if", "then", "elif", "else", "while", "until", "do"}
SHELL_INTERPRETERS = {"sh", "bash", "zsh", "dash", "ksh"}
# Programs that run the command named after their own words (`find -exec` is read apart:
# git_commit_calls.runs_through_launcher).
LAUNCHER_PROGRAMS = ("xargs", "parallel", "watch", "flock")
# Container programs: `exec` and `run` run the command named after them inside a container.
CONTAINER_PROGRAMS = ("docker", "podman")
# Programs whose `exec` and `run` take a service, container or image (`docker` itself, and the compose launcher).
COMPOSE_PROGRAMS = ("docker", "docker-compose")
# Other programs that run their arguments as commands, locally or on another host.
ARGUMENT_RUNNER_PROGRAMS = ("eval", "su", "script", "ssh")
# A command text that names one of these as a word may run code the parser does not read: a shell's `-c` text, an
# `eval` argument, a command run through another program or on another host. A quoted mention counts, except a
# shell name right after a `|` or a backslash: that is a regex alternative such as `(py|sh)`. A name that is part of
# a file name (`run.sh`, `~/.ssh/config`, `deploy-script.py`, `ssh-keygen`) is no runner: a `.` before it or a `.` or
# `-` after it joins it to a longer word.
CODE_RUNNERS = re.compile(
    r"(?<![|\\.])\b(" + "|".join(sorted(SHELL_INTERPRETERS)) + r")(?=\.exe\b|(?![\w.-]))"
    r"|(?<!\.)\b(" + "|".join(ARGUMENT_RUNNER_PROGRAMS + LAUNCHER_PROGRAMS) + r")(?=\.exe\b|(?![\w.-]))"
    r"|\bgit\b[^\n]*\brebase\b[^\n]*\s(--exec|-x)\b"
    r"|\bfind\b[^\n]*\s-exec(dir)?\b"
    r"|\b(" + "|".join(CONTAINER_PROGRAMS) + r")\b[^\n]*\b(exec|run)\b"
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
    # zsh precommand modifiers: each runs the command after it (`-` is a login-shell marker, a lone word).
    "nocorrect": set(),
    "noglob": set(),
    "-": set(),
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
# whose next word is code (`-c`, `-Bc`, `-le`), the letters whose attached value ends the walk with no code
# (`-mcProfile`; the next word is not consumed), and the long flags that take the next word as code. nodejs is the
# node family.
INTERPRETER_FAMILIES = {
    "python": {"name": r"python[\d.]*", "no_stdin_code_flags": {"-m", "-V", "-VV", "--version", "-h", "--help"},
               "value_options": {"-W", "-X", "-Q"}, "inline_code_letters": "c", "attached_value_letters": "m",
               "inline_code_flags": set()},
    "perl": {"name": r"perl", "no_stdin_code_flags": {"-v", "-V", "--version", "-h", "--help"},
             "value_options": {"-I", "-M", "-C"}, "inline_code_letters": "eE", "attached_value_letters": "xF",
             "inline_code_flags": set()},
    "ruby": {"name": r"ruby", "no_stdin_code_flags": {"-v", "--version", "-h", "--help"},
             "value_options": {"-I", "-r", "-C", "-E"}, "inline_code_letters": "e", "attached_value_letters": "xFK",
             "inline_code_flags": set()},
    "node": {"name": r"node(?:js)?", "no_stdin_code_flags": {"-v", "--version", "-h", "--help"},
             "value_options": {"-r", "--require", "--import", "-C", "--conditions"}, "inline_code_letters": "ep",
             "attached_value_letters": "", "inline_code_flags": {"--print", "--eval"}},
    "php": {"name": r"php", "no_stdin_code_flags": {"-v", "--version", "-h", "--help"},
            "value_options": {"-d", "-c", "-r"}, "inline_code_letters": "r", "attached_value_letters": "f",
            "inline_code_flags": set()},
}
INTERPRETER = re.compile("|".join(family["name"] for family in INTERPRETER_FAMILIES.values()), re.I)
MANAGE_SCRIPT = "manage.py"
# Words that name stdin as the program file of an interpreter, like `-`.
STDIN_PROGRAM_FILES = {"-", "/dev/stdin", "/dev/fd/0", "/proc/self/fd/0"}
# Redirections that carry code inside the command: a heredoc or a here-string. A file read with `<` is a script file,
# as in `python3 <file>`.
STDIN_CODE_REDIRECTIONS = {"<<", "<<<"}


def code_letter_position(word, family):
    # The index in word of the code letter of a short-flag cluster of the INTERPRETER_FAMILIES entry `family` (`-c`,
    # `-Bc`), or None. The cluster is read one letter at a time: a value option ends it, because the rest of the word
    # is its value (`-rdotenv/config`, `-Xtracemalloc`).
    if not re.match(r"-[a-zA-Z]", word):
        return None
    for position, letter in enumerate(word[1:], start=1):
        if letter in family["inline_code_letters"]:
            return position
        if letter in family["attached_value_letters"]:
            return None  # the rest of the word is this option's value, not a code letter (`-mcProfile`, `-fw.php`)
        if not letter.isalpha() or "-" + letter in family["value_options"]:
            return None
    return None


def is_inline_code_option(word, family):
    # True when word is an option of the INTERPRETER_FAMILIES entry `family` that carries code: a short-flag cluster
    # ending in a code letter, or a long code flag. Code attached to the cluster (`-cprint(1)`) counts.
    if word in family["inline_code_flags"]:
        return True
    return code_letter_position(word, family) is not None


def attached_inline_code(word, family):
    # The code attached to the code letter of an option for which is_inline_code_option is True (`-cprint(1)` gives
    # `print(1)`); "" when the code is the next word (`-c`, `-Bc`) or the option is a long flag.
    if word in family["inline_code_flags"]:
        return ""
    position = code_letter_position(word, family)
    if position is None:
        return ""
    return word[position + 1:]


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


def is_redirect_word(word):
    """True when the word starts with a redirect operator; one that starts with a quote or backslash never does."""
    return bool(REDIRECT_WORD.match(word))


def redirect_takes_next_word(word):
    """True when the redirect word has no target of its own, so the next word is its target."""
    return bool(BARE_REDIRECT_WORD.match(word))


def kept_outside_redirections(word_shapes):
    """The words of (word, shape) pairs with each redirection dropped: a word whose shape is a redirect, and the next
    word when the redirect has no target of its own (`>` `main`). The shape is what the redirect is read from."""
    kept = []
    skip_target = False
    for word, shape in word_shapes:
        if skip_target:
            skip_target = False
            continue
        if is_redirect_word(shape):
            skip_target = redirect_takes_next_word(shape)
            continue
        kept.append(word)
    return kept


def without_redirection_words(words, blanked_words):
    """The words with each redirection dropped. `blanked_words` are the same words with each quoted string blanked; a
    redirect is read from them, so a quoted `'>'` stays a plain word."""
    return kept_outside_redirections(zip(words, blanked_words, strict=True))


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
    run of operator characters it cannot sort (`<|`). `>|` and the adjacent `>!` are output redirections."""
    return [(words, redirections) for words, redirections, _piped in parse_piped_commands(command)]


def parse_piped_commands(command):
    """Like parse_simple_commands, but each command is a triple (words, redirections, piped): piped is True when
    the command reads from a pipe, that is, a `|` or `|&` comes right before it. Raises ValueError as
    parse_simple_commands does."""
    return _read_commands(command, posix=True)


def parse_raw_simple_commands(command):
    """The raw words of each simple command in a shell command, split where parse_simple_commands splits, with the
    quotes still in place and each redirection left out. Raises ValueError as parse_simple_commands does. A word that
    glues a quoted part to more text (`a"b c"d`), or holds a backslash-escaped blank (`a\\ b`), is cut differently
    than parse_simple_commands cuts it, so a caller pairs a raw command with a parsed one by comparing their words,
    and has a fallback for no match."""
    return [words for words, _redirections, _piped in _read_commands(command, posix=False) if words]


def _read_commands(command, posix):
    if HIDDEN_OPERATOR.search(command):
        raise ValueError("operator character inside quotes or after a backslash")
    if SPACED_REDIRECT_NUMBER.search(command):
        raise ValueError("a number, a space and a redirection")

    lexer = shlex.shlex(with_bang_clobber_as_pipe(command), posix=posix, punctuation_chars="();<>|&\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    reader = _PipedCommandReader()
    for token in lexer:
        reader.read(token)
    return reader.finish()


def with_bang_clobber_as_pipe(command):
    """The command with the `!` of each unquoted adjacent clobber operator (`>!`, `>>!`, `>&!`, `>>&!`) written as
    `|`, so the lexer reads one operator. `> !name` is a `>` and a file named `!name`, and is left as it is."""
    characters = list(command)
    for found in unquoted_matches(ADJACENT_BANG_CLOBBER, command):
        characters[found.end() - 1] = "|"
    return "".join(characters)


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
        elif token and (characters <= REDIRECT_CHARS or CLOBBER_TOKEN.fullmatch(token)):
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
    if not words:
        return None

    group_words = ("compose", "container") if words[0] == "docker" else ()
    found = container_subcommand(words, COMPOSE_PROGRAMS, group_words, ("exec", "run"))
    if found is None:
        return None
    # The word after the options is the service, container or image; the rest is the command.
    return min(found[1] + 1, len(words))


def container_subcommand(words, programs, group_words, verbs):
    """(verb_index, target_index) of a docker or podman call whose words start at the program: the index of the verb
    after the global options and an optional group word, and the index of the service, container or image after the
    verb's own options (len(words) when the call names none). None when the program is not in `programs` or the verb
    is not in `verbs`."""
    if not words or words[0] not in programs:
        return None
    index = skip_options(words, 1, DOCKER_VALUE_OPTIONS, clusters_take_values=True)
    if index < len(words) and words[index] in group_words:
        index = skip_options(words, index + 1, DOCKER_VALUE_OPTIONS, clusters_take_values=True)
    if index >= len(words) or words[index] not in verbs:
        return None
    target_index = skip_options(words, index + 1, DOCKER_VALUE_OPTIONS, clusters_take_values=True)
    return index, target_index


class ContainerRun(NamedTuple):
    """Where a container run call sits in its words: `run_index` is the index of the `run` word, `image_index` the
    index of the image word, len(words) when the call names none."""
    run_index: int
    image_index: int


def container_run(words):
    """Where the `run` word and the image sit in a docker or podman `run` or `container run` call whose words start
    at the program, as a ContainerRun; image_index is len(words) when the call names no image. None when the words
    are not such a call."""
    found = container_subcommand(words, CONTAINER_PROGRAMS, ("container",), ("run",))
    if found is None:
        return None
    return ContainerRun(*found)


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


def one_letter_options(value_options):
    # The letters of the one-letter options (`-C`) in value_options.
    return {option[1] for option in value_options if len(option) == 2 and option[0] == "-"}


def first_value_letter(word, value_options):
    # The first letter of a short cluster (`-vC`) that is a one-letter option of value_options; None for a word that
    # is no cluster or holds none.
    if not is_short_cluster(word):
        return None
    position = len(flags_before_value(word, one_letter_options(value_options)))
    if position == len(word) - 1:
        return None
    return word[1 + position]


def value_letter_ends_cluster(word, value_letters):
    # True when a short cluster's first value-taking letter is its last, so the value is the next word (`-iC /dir`).
    return is_short_cluster(word) and len(flags_before_value(word, value_letters)) == len(word) - 2


def skip_options(words, index, value_options, clusters_take_values=False):
    # The index of the first word from index on that is no option: an option that takes a value is skipped with it.
    # With clusters_take_values, a short cluster that ends in a value letter takes the next word too.
    while index < len(words) and words[index].startswith("-"):
        takes_next = words[index] in value_options
        if clusters_take_values and value_letter_ends_cluster(words[index], one_letter_options(value_options)):
            takes_next = True
        index += 2 if takes_next else 1
    return index


# git's own options that take the next word as their value.
GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--super-prefix",
                     "--attr-source"}
GIT_GLOBAL_FLAGS = ("-p", "--paginate", "-P", "--no-pager", "--bare", "--no-replace-objects", "--literal-pathspecs",
                    "--glob-pathspecs", "--noglob-pathspecs", "--icase-pathspecs", "--no-optional-locks",
                    "--no-lazy-fetch", "--no-advice", "--exec-path")
# Options that take a value in the `--name=value` form; --exec-path takes one only in this form.
GIT_EQUALS_OPTIONS = GIT_VALUE_OPTIONS | {"--exec-path"}


def is_known_git_global_option(option):
    name, has_value, _ = option.partition("=")
    return option in GIT_GLOBAL_FLAGS or (bool(has_value) and name in GIT_EQUALS_OPTIONS)


def git_c_settings(options):
    """The `-c key=value` settings in git_options output, as {lowercased key: raw value}; the last one wins. A bare
    `-c key` is read by git as true, so it is stored as "true"; `-c key=` stays empty."""
    settings = {}
    for option, value in options:
        if option == "-c" and value is not None:
            key, equals, setting = value.partition("=")
            settings[key.lower()] = setting if equals else "true"
    return settings


def git_option_values(options, name):
    """The value of each `name` option in git_options output, in order, from `--name value` or `--name=value`."""
    for option, value in options:
        if option == name and value is not None:
            yield value
        elif option.startswith(name + "="):
            yield option.partition("=")[2]


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


def is_short_cluster(argument):
    """True for a bundle of short flags such as `-SW`; a bare `-` and a `--long` option are not."""
    return argument[:1] == "-" and argument[1:2] not in ("", "-")


def is_long_prefix(argument, option, shortest):
    """True when the argument is `option` or an abbreviation of it, at least as long as `shortest`, that git's option
    parser accepts."""
    return len(argument) >= len(shortest) and option.startswith(argument)


def flags_before_value(argument, value_letters):
    """The flag letters of a short cluster before the first letter that takes a value.

    `-sSTABLE` holds the value `STABLE` for `-s`, so its `S` is not the `-S` flag.
    """
    letters = argument[1:]
    for position, letter in enumerate(letters):
        if letter in value_letters:
            return letters[:position]
    return letters


def options_before_separator(arguments):
    """The arguments up to a bare `--`; what follows is a path, not an option."""
    if "--" in arguments:
        return arguments[:arguments.index("--")]
    return arguments


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


def without_flag_values(words, value_flags=(), takes_value=None):
    # The words with the value word after each of value_flags, or after each word takes_value accepts, dropped.
    # The flag itself stays.
    kept_words = []
    skip_value = False
    for word in words:
        if skip_value:
            skip_value = False
            continue
        skip_value = word in value_flags or (takes_value is not None and takes_value(word))
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
    rest = words[skip_options(words, 1, WRAPPER_VALUE_OPTIONS[name], clusters_take_values=True):]
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
        simple_commands = split_simple_commands(join_line_continuations(command))
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
    words = closed_segment_words(segment)
    if words is None:
        return words_by_blank(segment)
    return words


def words_by_blank(text):
    """The words of text split on blanks and newlines, quotes ignored."""
    return [word for word in re.split(r"[ \t\n]+", text) if word]


def closed_segment_words(segment):
    """The words of one command text with the quotes removed, or None when a quote never closes (the text is cut off,
    so no word after the quote can be told from the text inside it)."""
    try:
        return shlex.split(segment)
    except ValueError:
        return None


def words_without_redirections(text):
    """The words of one command text with the quotes removed and each redirection left out, the target of a bare `>`
    with it, or None when a quote never closes. A redirection is a blank-separated piece of the raw text that starts
    with its operator: a quoted or escaped look-alike (`'>&'`, `\\>`, `'2>'`) starts with a quote or a backslash, so it
    stays a word."""
    words = []
    for raw_word in raw_words_without_redirections(text):
        piece = closed_segment_words(raw_word)
        if piece is None:
            return None
        words += piece
    return words


def raw_words_without_redirections(text):
    """The blank-separated words of one command text with quotes kept and each redirection left out, the target of a
    bare `>` with it."""
    quoted = quoted_positions(text)
    raw_words = _raw_words(text, quoted)
    word_shapes = list(zip(raw_words, raw_words, strict=True))
    return kept_outside_redirections(word_shapes)


def _raw_words(text, quoted):
    # The pieces of the text between the blanks that sit outside quotes and are not escaped, quotes still in place.
    raw_words = []
    current = ""
    for index, character in enumerate(text):
        if character in " \t\r\n" and index not in quoted:
            if current:
                raw_words.append(current)
            current = ""
            continue
        current += character
    if current:
        raw_words.append(current)
    return raw_words


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


def continues_list(operator, code_text):
    """True when a newline after the step text (comments cut) goes on with the list: the step ends in `|&` (no
    operator here, so it ends its step's text), or it is blank after an operator that takes a right side."""
    if code_text.rstrip().endswith("|&"):
        return True
    return operator in LINE_CONTINUING_OPERATORS and not code_text.strip()


def split_command_steps(command):
    """Split a shell command on ||, &&, | ; newline and a lone & into (operator, step) pairs. The operator is the one
    that comes before the step; the first step has "". A newline counts as ";", except right after `&&`, `||` or `|`
    (only blanks or a comment between): there the next line continues the list, so the step goes on across it. A step
    that ends in `|&` also goes on across the newline. An operator inside single or double quotes, or after a
    backslash, stays in its step."""
    quoted = quoted_positions(command)
    steps = []
    operator = ""
    step_start = 0
    for match in OPERATOR.finditer(command):
        if match.start() in quoted:
            continue
        step_text = command[step_start:match.start()]
        if match.group() == "\n" and continues_list(operator, strip_comments(step_text)):
            continue
        steps.append((operator, step_text))
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


def substitution_bounds(text):
    """(start, end) of the text inside each outermost `$(...)` and backtick pair in text that is not in single quotes,
    a comment or after a backslash; one inside double quotes counts. A span that never closes runs to the end of the
    text."""
    hidden = quoted_positions(text, unclosed_is_quoted=False)
    bounds = []
    index = 0
    while index < len(text):
        if index in hidden:
            index += 1
            continue

        if text.startswith("$(", index):
            close = matching_parenthesis(text, index + 1, hidden)
            end = len(text) if close is None else close
            bounds.append((index + 2, end))
            index = end
        elif text[index] == "`":
            end = _backtick_span_end(text, index)
            bounds.append((index + 1, end))
            index = end
        index += 1
    return bounds


def process_substitution_bounds(text):
    """(start, end) of the text inside each outermost `>(...)` and `<(...)` pair in text that is not quoted, in a
    comment or after a backslash. The shell runs that text as a command. A span that never closes runs to the end of
    the text."""
    hidden = quoted_positions(text, unclosed_is_quoted=False)
    bounds = []
    index = 0
    while index < len(text) - 1:
        opens_process = text[index] in "<>" and text[index + 1] == "("
        if index in hidden or not opens_process:
            index += 1
            continue

        close = matching_parenthesis(text, index + 1, hidden)
        end = len(text) if close is None else close
        bounds.append((index + 2, end))
        index = end + 1
    return bounds


def substitution_spans(text):
    """The text inside each outermost `$(...)` and backtick pair in text that is not in single quotes, a comment or
    after a backslash; one inside double quotes counts. A span that never closes runs to the end of the text."""
    return [text[start:end] for start, end in substitution_bounds(text)]


def without_substitution_bodies(text):
    """The text with the inside of each outermost substitution (see substitution_spans) replaced by one `x`, so no
    blank, glob character or quote of a body shows to a reader of the words around it."""
    pieces = []
    position = 0
    for start, end in substitution_bounds(text):
        pieces.append(text[position:start])
        pieces.append("x")
        position = end
    pieces.append(text[position:])
    return "".join(pieces)


def without_substitutions(text):
    """The text with each outermost `$(...)` and backtick span, its opener and closer included, replaced by one `x`,
    so no `)` of a span ends a simple command that the span sits in (`F=$(git ...)/stop.md`)."""
    pieces = []
    position = 0
    for start, end in substitution_bounds(text):
        opener_length = 2 if text[start - 1] == "(" else 1
        pieces.append(text[position:start - opener_length])
        pieces.append("x")
        position = end + 1
    pieces.append(text[position:])
    return "".join(pieces)


PARENTHESIS_DEPTH_CHANGE = {"(": 1, ")": -1}


def matching_parenthesis(text, open_index, hidden):
    """The index of the `)` closing the `(` at open_index, skipping hidden positions; None when it never closes."""
    depth = 0
    for position in range(open_index, len(text)):
        if position in hidden:
            continue
        depth += PARENTHESIS_DEPTH_CHANGE.get(text[position], 0)
        if depth == 0:
            return position
    return None


def _backtick_span_end(text, start):
    # The index of the backtick that closes the one at start, or the end of the text when it never closes.
    end = text.find("`", start + 1)
    return len(text) if end == -1 else end


# The `-c` settings that move no directory, in lower case: git reads section and key names without case.
DIRECTORY_FREE_CONFIG = ("alias.", "core.editor=", "sequence.editor=", "user.name=", "user.email=")


def git_c_directory(words, directory):
    """The directory a git call in `words` runs in, from `directory`, moved by each `-C <dir>` before the subcommand
    (`~` expanded; a `-c alias.<name>=<value>`, `-c core.editor=<value>`, `-c sequence.editor=<value>`,
    `-c user.name=<value>` or `-c user.email=<value>` moves nothing). None when git's options are ones the gate does
    not follow: `--git-dir`, `--work-tree`, `--config-env`, any other `-c`, a `-C` with no or an empty value, or an
    option git is not known to have."""
    options, _index = git_options(words)
    for option, value in options:
        if option == "-C":
            if not value:
                return None
            directory = os.path.normpath(os.path.join(directory, path_word(value)))
            continue
        if option == "-c" and (value or "").lower().startswith(DIRECTORY_FREE_CONFIG):
            continue  # moves no directory; the caller reads what an alias expands to
        if not is_known_git_global_option(option) or option.startswith(("--git-dir", "--work-tree", "--config-env")):
            return None
    return directory


def word_moves_directory(word, move_letter, wrapper):
    # True for `--chdir`, `-<move_letter>...`, or a short cluster whose first value letter is move_letter.
    if word.startswith("--chdir") or word.startswith("-" + move_letter):
        return True
    letter = first_value_letter(word, WRAPPER_VALUE_OPTIONS[wrapper])
    return letter == move_letter


def wrapper_moves_directory(words):
    """True when an `env` or `sudo` wrapper of the simple command `words` runs the command in another directory:
    `env -C <dir>`, `env -C<dir>`, `env --chdir`, `sudo -D <dir>`, `sudo -D<dir>`, `sudo --chdir`, and a short
    cluster whose first value letter is that letter (`env -vC <dir>`). (`sudo -C` is close-from, not a directory
    move.)"""
    word_lists = list(_peeled_word_lists(words))
    for before, after in itertools.pairwise(word_lists):
        wrapper = os.path.basename(before[0])
        if wrapper not in ("env", "sudo"):
            continue
        move_letter = "C" if wrapper == "env" else "D"
        wrapper_words = before[1:len(before) - len(after)]
        if any(word_moves_directory(word, move_letter, wrapper) for word in wrapper_words):
            return True
    return False

