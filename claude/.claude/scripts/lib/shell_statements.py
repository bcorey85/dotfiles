"""Read a shell command as statements of words, ignoring heredoc bodies (except one fed to a shell interpreter, which
is code, and the `$(...)` and backtick spans of an unquoted one, which the shell runs), quoted strings and comments."""
import os
import pathlib
import re
import shlex
from typing import NamedTuple

import shell_command
import shell_quoting

SKIP_WORDS = {"do", "then", "else", "elif", "if", "!", "time"}
# More programs that run their argument or stdin as code, or are git itself, so a path to one is no script run.
OTHER_CODE_RUNNING_PROGRAMS = ("git", "find", "fish", "busybox", "csh", "tcsh", "mksh", "nu", "pwsh", "awk", "gawk",
                               "sed", "expect", "runuser", "sg", "tmux", "nix-shell")
# A path to one of these runs its argument or stdin as commands (or is git), so it is no script run.
NOT_SCRIPT_PROGRAMS = (
    shell_command.SHELL_INTERPRETERS
    | set(shell_command.LAUNCHER_PROGRAMS)
    | set(shell_command.ARGUMENT_RUNNER_PROGRAMS)
    | set(shell_command.CONTAINER_PROGRAMS)
    | set(OTHER_CODE_RUNNING_PROGRAMS)
)
# Shell builtins that run a file's text as commands.
SOURCE_WORDS = ("source", ".")
# Scripts in the trusted toolkit folders that run `exec <interpreter> "$@"`: each is read as that interpreter.
INTERPRETER_LAUNCHER_SCRIPTS = {"hook-python": "python3"}
# A later word of these flags, alone or as `<flag>=<value>`, makes a run no script run: `review_fix.py launch --test`
# and `review_loop_script.py --gate-command` run the value as a command, and a test runner runs files as code.
COMMAND_VALUE_FLAGS = ("--test", "--gate-command")
# The delimiter is the whole shell word after `<<`: unquoted characters, quoted strings and escapes.
HEREDOC = re.compile(r"""(?<!<)<<(?!<)-?[ \t]*((?:[^\s|&;()<>'"\\]|\\.|'[^']*'|"(?:[^"\\]|\\.)*")+)""")
DELIMITER_PART = re.compile(r"""\\(.)|'([^']*)'|"((?:[^"\\]|\\.)*)"|([^'"\\]+)""")
# A `((` or `$((`, found at each position, so that a span inside another is found too.
ARITHMETIC_OPENER = re.compile(r"\$?\((?=\()")
QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")
QUOTE_MARK = re.compile("\x01(\\d+)\x01")
COMMAND_SUBSTITUTION = re.compile(r"\$\(([^()]*)\)")
COMPOUND_OPENER = re.compile(r"[{(]|(?<![\w.-])(?:do|then|else)(?![\w.-])")
# The step operators of shell_command (a `&` inside a redirection is none), `|&` and the parentheses.
SEPARATORS = re.compile(shell_command.OPERATOR.pattern + r"|\|&|\(|\)")
STATEMENT_SPLIT = re.compile("(" + SEPARATORS.pattern + ")")
ASSIGNMENT = re.compile(r"^[A-Za-z_]\w*=")
PIPE_BOTH = re.compile(r"\|&")


def split_on_pipe_both(core):
    """The parts of a step's text on each `|&` outside quotes; every part after the first reads from a pipe."""
    parts = []
    part_start = 0
    for found in shell_quoting.unquoted_matches(PIPE_BOTH, core):
        parts.append(core[part_start:found.start()])
        part_start = found.end()
    parts.append(core[part_start:])
    return parts


def arithmetic_spans(text, start=0):
    """(begin, end) of each `$((...))` or `((...))` in text, from start on, that is arithmetic: the outer `(` closes
    at the end and the inner `(` closes at the last character before it (`is_arithmetic_span`). A `((cmd) > f)` or
    `$((cmd) )` is a subshell or command substitution and is no span. A span may hold another. An opener in quotes
    or a comment is no span."""
    hidden = shell_quoting.quoted_positions(text, unclosed_is_quoted=False)
    spans = []
    for opener in ARITHMETIC_OPENER.finditer(text, start):
        outer = opener.end() - 1
        if outer in hidden:
            continue
        close = shell_command.matching_parenthesis(text, outer, hidden)
        if close is None or not is_arithmetic_span(text[outer + 1:close]):
            continue
        spans.append((opener.start(), close + 1))
    return spans


def arithmetic_positions(text, start=0):
    """The positions in text, from start on, that lie inside `$((...))` or `((...))`: an operator scan skips them."""
    positions = set()
    for begin, end in arithmetic_spans(text, start):
        positions.update(range(begin, end))
    return positions


def is_arithmetic_span(span):
    """Whether the text between the `$(` and the final `)` of a `$((...))` is arithmetic: it opens with the inner `(`
    and that `(` closes at the span's last character. When it closes earlier (`(cmd) `), zsh reads a command
    substitution that runs cmd."""
    quoted = shell_quoting.quoted_positions(span)
    return shell_command.matching_parenthesis(span, 0, quoted) == len(span) - 1


def substitution_pieces(body):
    """The `$(...)` and backtick spans of a heredoc body's lines, each wrapped in parentheses as its own command."""
    body_text = "\n".join(body)
    pieces = []
    for _start, _end, span in code_spans(body_text):
        pieces += ["(", span, ")"]
    return pieces


def strip_heredocs(command):
    """The command with each heredoc body and its terminator line cut out, except that the body of a heredoc fed to
    a shell interpreter (`bash <<EOF`) stays: it is code, and so does each `$(...)` and backtick span in the body of
    a heredoc whose delimiter is unquoted: the shell runs those. A line may open several heredocs; their bodies
    follow in order. The delimiter is the whole shell word, quotes removed. A `<<` inside quotes, a comment or
    arithmetic and a `<<<` here-string open none; a heredoc with no terminator line is not cut. A kept body is
    wrapped in `(` and `)` lines: the shell runs it in its own process."""
    def keep_bodies(line, lines, index, heredocs):
        bodies = heredoc_bodies(lines, index, [delimiter for delimiter, _quoted in heredocs])
        if not heredocs or bodies is None:
            return None

        added = []
        shell_body = opens_shell_heredoc(line)
        for (_delimiter, quoted), body in zip(heredocs, bodies, strict=True):
            if shell_body:
                added += ["(", *body, ")"]
            elif not quoted:
                added += substitution_pieces(body)
        return added, sum(len(body) + 1 for body in bodies)

    return rewrite_heredoc_lines(command, keep_bodies)


def shell_code(command):
    """The text a gate reads from a Bash command: heredoc bodies cut as strip_heredocs does (a body fed to a shell, and
    the substitution spans of an unquoted body, stay), comments cut, then each backslash-newline joined. Comments go
    before the join: a `\\` ending a comment line is literal in zsh, so it must not pull the next
    line into the comment."""
    without_heredocs = strip_heredocs(command)
    uncommented = shell_quoting.strip_comments(without_heredocs)
    return shell_quoting.join_line_continuations(uncommented)


def outside_heredoc_bodies(command, transform):
    """The command with transform(text) applied to each run of lines that are no heredoc body or terminator line;
    those lines stay as written, so a quote in a body does not change the quote state of the lines after it."""
    body_lines = set()

    def note_bodies(line, lines, index, heredocs):
        bodies = heredoc_bodies(lines, index, [delimiter for delimiter, _quoted in heredocs])
        if not heredocs or bodies is None:
            return None

        skipped = sum(len(body) + 1 for body in bodies)
        body_lines.update(range(index, index + skipped))
        return [], skipped

    rewrite_heredoc_lines(command, note_bodies)
    pieces = []
    open_lines = []
    for number, line in enumerate(command.split("\n")):
        if number not in body_lines:
            open_lines.append(line)
            continue
        if open_lines:
            pieces.append(transform("\n".join(open_lines)))
            open_lines = []
        pieces.append(line)
    if open_lines:
        pieces.append(transform("\n".join(open_lines)))
    return "\n".join(pieces)


def strip_stored_heredocs(command):
    """The command with the body and terminator line of each heredoc cut out where the heredocs its line opens only
    store text: cat or tee writing a file, or a script run (`runs_script_file`). The `$(...)` and backtick spans of an
    unquoted body stay, wrapped in `(` and `)` lines, because the shell runs them. Every other heredoc stays as
    written, and so does every heredoc of a command that pipes out of a compound group (see pipes_out_of_compound):
    the group's output may feed a shell."""
    if pipes_out_of_compound(command):
        return command

    def cut_stored(line, lines, index, heredocs):
        if not heredocs:
            return None

        bodies = heredoc_bodies(lines, index, [delimiter for delimiter, _quoted in heredocs])
        if bodies is None or not stores_heredoc_text(line):
            return None

        added = []
        for (_delimiter, quoted), body in zip(heredocs, bodies, strict=True):
            if not quoted:
                added += substitution_pieces(body)
        return added, sum(len(body) + 1 for body in bodies)

    return rewrite_heredoc_lines(command, cut_stored)


def rewrite_heredoc_lines(command, handle):
    # Walk the lines, keeping each. For a line that holds `<<`, handle(line, lines, next_index, heredocs) returns None
    # to leave the following lines alone, or (lines to add after it, count of following lines to skip).
    lines = command.split("\n")
    kept = []
    index = 0
    while index < len(lines):
        line = lines[index]
        kept.append(line)
        index += 1
        if "<<" not in line:
            continue

        text = "\n".join(kept)
        heredocs = heredoc_openers(text, len(text) - len(line))
        result = handle(line, lines, index, heredocs)
        if result is None:
            continue

        added, skipped = result
        kept += added
        index += skipped
    return "\n".join(kept)


def stores_heredoc_text(line):
    # True when the line parses, a command on it takes a heredoc, and each such command reads it as data that no
    # later command is piped from.
    try:
        piped_commands = shell_command.parse_piped_commands(shell_quoting.strip_comments(line))
    except ValueError:
        return False

    takers = [position for position, (_words, redirections, _piped) in enumerate(piped_commands)
              if any(operator == "<<" for operator, _target in redirections)]
    if not takers:
        return False

    for position in takers:
        following = piped_commands[position + 1:position + 2]
        if following and following[0][2]:
            return False
        words, redirections, _piped = piped_commands[position]
        if not reads_heredoc_as_data(words, redirections):
            return False
    return True


def reads_heredoc_as_data(words, redirections):
    # cat or tee that writes a file, or a script run (`runs_script_file`): stdin is text it stores or reads.
    words = shell_command.command_after_wrappers(words)
    if not words:
        return False

    words = launcher_as_interpreter(words)
    program = os.path.basename(words[0])
    if program in {"cat", "tee"}:
        writes_file = any(shell_command.redirection_writes_file(operator, target) for operator, target in redirections)
        tee_file = program == "tee" and any(not word.startswith("-") for word in words[1:])
        return writes_file or tee_file
    is_interpreter = shell_command.INTERPRETER.fullmatch(program)
    if is_interpreter and shell_command.reads_code_from_stdin(words, redirections, False):
        return False
    return runs_script_file(words)


def names_command_value_flag(word):
    """True when the word is a flag of COMMAND_VALUE_FLAGS, alone or with its value attached by `=`."""
    flag = word.split("=", 1)[0]
    return flag in COMMAND_VALUE_FLAGS


def runs_script_file(words):
    """True when the simple command runs a script file, so its arguments and stdin are data for that script: an
    interpreter given a script file after value-taking options only, or a first word that is a path to a program in
    the installed toolkit's scripts folder, the toolkit this module is loaded from, or a skill's scripts folder (see
    trusted_script_path), when no later word names a program of NOT_SCRIPT_PROGRAMS or an interpreter (`mise exec --
    bash` runs that shell), and no later word is a flag of COMMAND_VALUE_FLAGS (names_command_value_flag: the value
    may run as a command). An interpreter
    that reads its code from stdin is no script run: reads_heredoc_as_data checks that before it calls this. A trusted
    program's argv and stdin are trusted as data, except a launcher of INTERPRETER_LAUNCHER_SCRIPTS, which is read as
    the interpreter it runs (see launcher_as_interpreter). Any other wrapper in those folders that runs its argument
    as code is not detected."""
    words = shell_command.command_after_wrappers(words)
    if not words:
        return False

    words = launcher_as_interpreter(words)
    passes_command_value = any(names_command_value_flag(word) for word in words[1:])
    if passes_command_value:
        return False

    program = os.path.basename(words[0])
    names_code_runner = any(is_code_running_program(word) for word in words[1:])
    if shell_command.INTERPRETER.fullmatch(program):
        return given_script_file_after_value_options(words) and not names_code_runner
    if "/" not in words[0]:
        return False
    return trusted_script_path(words[0]) and not names_code_runner


def is_code_running_program(word):
    """True when the word names a program of NOT_SCRIPT_PROGRAMS or an interpreter (shell_command.INTERPRETER)."""
    program = os.path.basename(word)
    return program in NOT_SCRIPT_PROGRAMS or bool(shell_command.INTERPRETER.fullmatch(program))


def launcher_as_interpreter(words):
    """The words with a trusted toolkit launcher of INTERPRETER_LAUNCHER_SCRIPTS replaced by the interpreter it runs,
    so the interpreter rules apply: a script file after options is a script run, inline code or stdin is not. Any
    other words are returned as they are."""
    if not words or os.path.basename(words[0]) not in INTERPRETER_LAUNCHER_SCRIPTS:
        return words
    if not trusted_script_path(words[0]):
        return words
    return [INTERPRETER_LAUNCHER_SCRIPTS[os.path.basename(words[0])], *words[1:]]


def trusted_script_path(word):
    """True when the real path of the absolute path-form word (the home mark expanded, links and `..` resolved) lies
    in the scripts folder of the installed toolkit or of the toolkit this module is loaded from, or in
    `skills/<skill>/scripts/` beside either, all read by real path. A
    word with `$` or a backtick, a relative word, and a path elsewhere (the work tree, a plugin, a downloaded tool, a
    bin folder) are not trusted: they may run their arguments as code."""
    if "$" in word or "`" in word:
        return False
    expanded = os.path.expanduser(word)
    if not os.path.isabs(expanded):
        return False

    resolved = os.path.realpath(expanded)
    for toolkit_dir in toolkit_dirs():
        scripts_dir = os.path.realpath(os.path.join(toolkit_dir, "scripts")) + os.sep
        if resolved.startswith(scripts_dir):
            return True
        skills_dir = os.path.realpath(os.path.join(toolkit_dir, "skills")) + os.sep
        if in_skill_scripts(resolved, skills_dir):
            return True
    return False


def toolkit_dirs():
    """The toolkit folders whose scripts are trusted: the installed one under the home folder and the one this module
    sits in. The second root keeps a script path trusted when stow links each skill on its own, so the real path of
    a skill script no longer lies under the real path of the installed skills folder."""
    toolkit_dir = os.path.join(os.path.expanduser("~"), ".claude")
    own_dir = str(pathlib.Path(__file__).resolve().parents[2])
    return [toolkit_dir, own_dir]


def in_skill_scripts(resolved, skills_dir):
    """True when the resolved path lies in `<skills_dir><skill>/scripts/` (skills_dir ends with a separator)."""
    if not resolved.startswith(skills_dir):
        return False

    below_skills = resolved[len(skills_dir):].split(os.sep)
    return len(below_skills) > 2 and below_skills[1] == "scripts"


def blank_script_run_quotes(command):
    """The command with each quoted string emptied to `""` in each step that is one script run (see runs_script_file):
    its quoted arguments are data. Every other step stays as written, so does a step that a `|` follows when a later
    step of that pipeline names a code runner (its output may feed a shell), a step this reading cannot parse, and
    every step of a command that pipes out of a compound group (see pipes_out_of_compound): the group's steps are not
    read one by one."""
    if pipes_out_of_compound(command):
        return command

    steps = shell_command.split_command_steps(command)
    pieces = []
    for position, (operator, step) in enumerate(steps):
        # split_command_steps keeps `|&` inside its step, so that step is not one simple command and
        # blank_if_script_run leaves it as written.
        if feeds_code_runner(steps, position):
            pieces.append(operator + step)
            continue
        pieces.append(operator + blank_if_script_run(step))
    return "".join(pieces)


def feeds_code_runner(steps, position):
    """True when a `|` follows steps[position] and a later step of that pipeline (up to the next operator that is not
    `|`) names a code runner, which may read the step's output as code."""
    for operator, later_step in steps[position + 1:]:
        if operator != "|":
            return False
        if step_names_code_runner(later_step):
            return True
    return False


def step_names_code_runner(step):
    """True when a word of the step is a code runner: shell_command.names_code_runner, or any word of the step that is
    a program of NOT_SCRIPT_PROGRAMS (shells, launchers, argument runners; this covers `fish` and `nu`, which
    names_code_runner misses), an interpreter that reads code from stdin (`| python3`), or `source` or `.`
    (`| source /dev/stdin`). A step this reading cannot parse counts as one, and so does a simple command whose first
    word is an expansion (starts with `$` or a backtick)."""
    if shell_command.names_code_runner(step):
        return True
    try:
        simple_commands = shell_command.split_simple_commands(step)
    except ValueError:
        return True
    for words in simple_commands:
        # A command word that is an expansion (`$SHELL`, `${SHELL}`, `$(which sh)`, a backtick) may name any program.
        if words and words[0].startswith(("$", "`")):
            return True
    return any(is_code_running_program(word) or word in SOURCE_WORDS for words in simple_commands for word in words)


def pipes_out_of_compound(command):
    """True when the command has a `|` step operator and an unquoted compound opener (`{`, `(`, `do`, `then`,
    `else`): a `{ ...; } | sh` group or a loop's output may feed a shell, and the steps inside it are not split
    per group, so the caller reads the command as written. Quoted text and the body of a heredoc that
    strip_heredocs cuts do not count: JSON text in a heredoc body holds `{`, and quoted prose holds `do`."""
    unheredoced = strip_heredocs(command)
    if not any(operator == "|" for operator, _step in shell_command.split_command_steps(unheredoced)):
        return False

    quoted = shell_command.quoted_positions(unheredoced)
    return any(match.start() not in quoted for match in COMPOUND_OPENER.finditer(unheredoced))


def blank_if_script_run(step):
    try:
        simple_commands = shell_command.split_simple_commands(step)
    except ValueError:
        return step

    if len(simple_commands) != 1 or not runs_script_file(simple_commands[0]):
        return step

    return QUOTED.sub('""', step)


def given_script_file_after_value_options(words):
    # True when the interpreter's options are all value-taking ones and a script file follows them. Any other option
    # (-i, -d, -m, --interactive) may read stdin as code, so the body stays readable. An inline-code option takes
    # code as its value (`php -r 'system(...)' x`): the word after it is no script file, even when the family also
    # lists the option as value-taking.
    family = shell_command.interpreter_family(words[0])
    rules = shell_command.INTERPRETER_FAMILIES[family]
    value_options = rules["value_options"]
    index = 1
    while index < len(words):
        word = words[index]
        if not word.startswith("-"):
            return True
        if shell_command.is_inline_code_option(word, rules):
            return False
        if word not in value_options:
            return False
        index += 2
    return False


def heredoc_bodies(lines, start, delimiters):
    # The body lines of each heredoc a line opens, in order, from lines[start:]; each ends at the first line that is
    # its delimiter. None when a terminator line is missing.
    bodies = []
    position = start
    for delimiter in delimiters:
        body = []
        while position < len(lines) and lines[position].strip() != delimiter:
            body.append(lines[position])
            position += 1
        if position == len(lines):
            return None
        position += 1
        bodies.append(body)
    return bodies


def code_spans(body):
    # (start offset, end offset, text) of each outermost `$(...)` and backtick span in body: the shell runs them.
    # The text is body[start:end]. A `\$` and a `\`` are plain text.
    spans = []
    index = 0
    while index < len(body):
        character = body[index]
        if character == "\\":
            index += 2
            continue
        if character == "$" and body[index + 1:index + 2] == "(":
            depth = 0
            for end in range(index + 1, len(body)):
                depth += {"(": 1, ")": -1}.get(body[end], 0)
                if depth == 0:
                    break
            spans.append((index + 2, end, body[index + 2:end]))
            index = end
        elif character == "`":
            end = body.find("`", index + 1)
            if end == -1:
                end = len(body)
            spans.append((index + 1, end, body[index + 1:end]))
            index = end
        index += 1
    return spans


def opens_shell_heredoc(line):
    # True when a command on the line takes a heredoc and runs a shell interpreter. A line this reading cannot parse
    # counts as a shell when any of its words names one: its body is kept and read as commands.
    try:
        piped_commands = shell_command.parse_piped_commands(shell_quoting.strip_comments(line))
    except ValueError:
        words = re.split(r"[\s|&;()<>]+", line)
        return any(os.path.basename(word.strip("'\"")) in shell_command.SHELL_INTERPRETERS for word in words)
    return any(shell_command.runs_shell(words) and any(operator == "<<" for operator, _target in redirections)
               for words, redirections, _piped in piped_commands)


def heredoc_openers(text, line_start):
    # (delimiter, quoted) for each heredoc the last line of text opens, in order: the line starts at line_start. A
    # `<<` inside quotes (also quotes that open on an earlier line), a comment or arithmetic opens none. quoted is
    # True when any part of the delimiter word is quoted: the body then holds no substitution.
    hidden_positions = shell_quoting.quoted_positions(text)
    hidden_positions.update(arithmetic_positions(text, line_start))
    openers = []
    for found in HEREDOC.finditer(text, line_start):
        if found.start() in hidden_positions:
            continue
        word = found.group(1)
        openers.append((delimiter_text(word), bool(re.search(r"""['"\\]""", word))))
    return openers


def delimiter_text(word):
    # The shell word with its quotes and escapes removed.
    parts = []
    for found in DELIMITER_PART.finditer(word):
        escaped, single, double, plain = found.groups()
        parts.append(escaped or single or (re.sub(r"\\(.)", r"\1", double) if double is not None else plain or ""))
    return "".join(parts)


def clean(command, quotes=None):
    """The command with heredoc bodies, quoted strings and comments blanked. When `quotes` is a list, each quoted
    string is replaced by a QUOTE_MARK word part holding its index in `quotes`, and the string is appended there."""
    without_heredocs = strip_heredocs(command)
    if quotes is None:
        without_quotes = QUOTED.sub('""', without_heredocs)
    else:
        without_quotes = QUOTED.sub(lambda found: marked_quote(found.group(), quotes), without_heredocs)
    without_comments = shell_quoting.strip_comments(without_quotes)
    return COMMAND_SUBSTITUTION.sub(lambda match: "$<" + match.group(1).replace(" ", "\x00") + ">", without_comments)


def marked_quote(quoted, quotes):
    # The quoted string's content (quotes removed, escapes in double quotes resolved) goes into quotes; the mark
    # that stands for it has no space, separator or quote character.
    inner = quoted[1:-1]
    if quoted[0] == '"':
        inner = re.sub(r'\\(["\\$`])', r"\1", inner)
    quotes.append(inner)
    return f"\x01{len(quotes) - 1}\x01"


def without_leading_noise(words, kept_words=()):
    """The words with the leading words of SKIP_WORDS (do, then, else, if, elif, `!`, `time`) and env assignments
    dropped, except the words in `kept_words`."""
    while words and words[0] not in kept_words and (words[0] in SKIP_WORDS or ASSIGNMENT.match(words[0])):
        words = words[1:]
    return words


def statements(command, quotes=None):
    """Each statement of the command as its list of words, split on every separator (SEPARATORS), with the leading
    words of without_leading_noise dropped. A list in `quotes` is filled as clean() describes, and the words then
    hold quote marks."""
    parsed = []
    for index, piece in enumerate(STATEMENT_SPLIT.split(clean(command, quotes))):
        if index % 2 == 1:
            continue
        words = without_leading_noise(piece.split())
        if words:
            parsed.append(words)
    return parsed


class WordPair(NamedTuple):
    # The statement's words with each quoted string blanked to `""`, and the same words with the quotes removed.
    blanked: list
    resolved: list


def statement_word_pairs(command):
    # Each statement of the command as a WordPair; the two lists have the same length.
    quotes = []
    pairs = []
    for words in statements(command, quotes=quotes):
        pairs.append(word_pair(words, quotes))
    return pairs


def word_pair(words, quotes):
    # The WordPair of one statement's words; `quotes` is the list clean() filled.
    blanked = [QUOTE_MARK.sub('""', word) for word in words]
    resolved = [resolved_word(word, quotes) for word in words]
    return WordPair(blanked, resolved)


def open_statement_word_pair(prefix):
    """The WordPair of the statement still open at the end of `prefix`: the words after its last separator, leading
    words of without_leading_noise dropped. Empty lists when `prefix` ends at a separator. `prefix` must close each
    quote it opens."""
    quotes = []
    pieces = STATEMENT_SPLIT.split(clean(prefix, quotes))
    words = without_leading_noise(pieces[-1].split())
    return word_pair(words, quotes)


ANSI_C_ESCAPE = re.compile(r"\\(x[0-9A-Fa-f]{1,2}|u[0-9A-Fa-f]{1,4}|U[0-9A-Fa-f]{1,8}|[0-7]{1,3}|.)", re.DOTALL)
MAX_CODE_POINT = 0x10FFFF
ANSI_C_SINGLE = {"a": "\a", "b": "\b", "e": "\x1b", "E": "\x1b", "f": "\f", "n": "\n", "r": "\r", "t": "\t",
                 "v": "\v"}


def decode_ansi_c_escape(found):
    body = found.group(1)
    if body[0] in "xuU" and len(body) > 1:
        code_point = int(body[1:], 16)
        if code_point > MAX_CODE_POINT:
            return found.group(0)
        return chr(code_point)
    if body[0] in "01234567":
        return chr(int(body, 8) & 0xFF)
    return ANSI_C_SINGLE.get(body, body)


def decode_ansi_c(content):
    # The text of a `$'...'` string as bash reads it: \xHH, \NNN, \uHHHH, \n and the like become their characters.
    return ANSI_C_ESCAPE.sub(decode_ansi_c_escape, content)


ANSI_C_STRING = re.compile(r"\$'((?:[^'\\]|\\.)*)'", re.DOTALL)


def without_ansi_c_quotes(command):
    """The command with each unquoted `$'...'` string replaced by its decoded text, shell-quoted (shlex.quote), so a
    reader that splits words with shlex (which keeps the `$`) sees the word the shell runs (`git $'commit'` reads as
    `git commit`). A `$'` inside quotes or a comment stays."""
    pieces = []
    position = 0
    for start in shell_quoting.ansi_c_quote_starts(command):
        found = ANSI_C_STRING.match(command, start)
        if found is None:
            continue
        pieces.append(command[position:start])
        pieces.append(shlex.quote(decode_ansi_c(found.group(1))))
        position = found.end()
    pieces.append(command[position:])
    return "".join(pieces)


def resolved_word(word, quotes):
    """The word as the shell reads it: each quoted string put back without its quotes, a `$` before a quote
    (`$'--hard'`) dropped with its escapes decoded, and each backslash outside quotes removed from the character
    it escapes."""
    parts = []
    position = 0
    for mark in QUOTE_MARK.finditer(word):
        before = re.sub(r"\\(.)", r"\1", word[position:mark.start()])
        position = mark.end()
        content = quotes[int(mark.group(1))]
        if before.endswith("$"):
            content = decode_ansi_c(content)
        parts.append(before.removesuffix("$"))
        parts.append(content)
    parts.append(re.sub(r"\\(.)", r"\1", word[position:]))
    return "".join(parts)
