"""Read a shell command line as steps joined by operators, without running or fully parsing it."""
import re
import shlex

SETUP_STEP = re.compile(r"^[ \t(]*(cd[ \t]|source[ \t]|\.[ \t]|export[ \t]|([^\W\d]\w*=[^ \t]*[ \t]*)+$)")
# `|&` (pipe both streams), `>&`, `&>` and `&&` are not a lone `&`; a lone `&` sends the step before it to the
# background.
OPERATOR = re.compile(r"(\|\||&&|\|(?!&)|(?<![>&|])&(?![&>])|;|\n)")
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
    run of operator characters it cannot sort (`>|`)."""
    if HIDDEN_OPERATOR.search(command):
        raise ValueError("operator character inside quotes or after a backslash")
    if SPACED_REDIRECT_NUMBER.search(command):
        raise ValueError("a number, a space and a redirection")

    lexer = shlex.shlex(command, posix=True, punctuation_chars="();<>|&\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    commands = []
    words = []
    redirections = []
    pending_operator = None
    for token in lexer:
        characters = set(token)
        if token and characters <= SEPARATOR_CHARS:
            if pending_operator is not None:
                redirections.append((pending_operator, ""))
            pending_operator = None
            if words or redirections:
                commands.append((words, redirections))
            words = []
            redirections = []
            continue
        if token and characters <= REDIRECT_CHARS:
            if pending_operator is not None:
                redirections.append((pending_operator, ""))
            if words and words[-1].isdigit():
                words.pop()
            pending_operator = token
            continue
        if token and characters <= SEPARATOR_CHARS | REDIRECT_CHARS:
            raise ValueError("unsorted operator characters: " + token)
        if pending_operator is not None:
            redirections.append((pending_operator, token))
            pending_operator = None
            continue
        words.append(token)
    if pending_operator is not None:
        redirections.append((pending_operator, ""))
    if words or redirections:
        commands.append((words, redirections))
    return commands


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

    index = skip_docker_options(words, 1)
    if words[0] == "docker" and index < len(words) and words[index] in ("compose", "container"):
        index = skip_docker_options(words, index + 1)
    if index >= len(words) or words[index] not in ("exec", "run"):
        return None

    # The word after the options is the service, container or image; the rest is the command.
    index = skip_docker_options(words, index + 1)
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
        elif word.startswith("--env="):
            value = word[len("--env="):]
        elif word.startswith("-e") and not word.startswith("--"):
            value = word[2:]
        elif word in DOCKER_VALUE_OPTIONS:
            index += 1
        if value:
            values.append(value)
    return values


def skip_docker_options(words, index):
    while index < len(words) and words[index].startswith("-"):
        index += 2 if words[index] in DOCKER_VALUE_OPTIONS else 1
    return index


def without_assignments(words):
    """The words with the leading NAME=value words dropped."""
    while words and "=" in words[0] and not words[0].startswith("-"):
        words = words[1:]
    return words


def split_command_steps(command):
    """Split a shell command on ||, &&, | ; newline and a lone & into (operator, step) pairs. The operator is the one
    that comes before the step; the first step has "". A newline counts as ";"."""
    pieces = OPERATOR.split(command)
    steps = [("", pieces[0])]
    for index in range(1, len(pieces), 2):
        operator = ";" if pieces[index] == "\n" else pieces[index]
        steps.append((operator, pieces[index + 1]))
    return steps


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
