"""interpreter_writes.py: find the git-tracked file an interpreter step (python, node, ruby, perl, ...) writes, by
tracing its inline code or untracked script file.

The shell write gate imports it after putting scripts/lib on sys.path."""
import os
import re
from collections import Counter, namedtuple

import script_utils
import shell_command
import shell_directory
from code_text import (
    SP,
    STRING_LITERAL,
    STRING_PREFIX_BEFORE_QUOTE,
    code_outside_strings,
    imported_names,
    receiver_text,
    split_arguments,
    statement_around,
    sub_outside_strings,
    top_level_positions,
    trim,
    tuple_fields,
    without_comments,
)
from hook_input import is_under_temp_dir
from inplace_edit import is_inplace
from shell_write_paths import is_git_tracked, resolve_target

INTERPRETER = re.compile(r"python[\d.]*|pypy[\d.]*|node|nodejs|ruby|perl|tsx|ts-node|bun|deno")
# The shell_command.INTERPRETER_FAMILIES entry that holds the flags of a program the gate reads.
PROGRAM_FAMILIES = (
    (re.compile(r"python[\d.]*|pypy[\d.]*"), "python"),
    (re.compile(r"node|nodejs|tsx|ts-node|bun|deno"), "node"),
    (re.compile(r"ruby"), "ruby"),
    (re.compile(r"perl"), "perl"),
)
# Deno takes its config file after these flags.
DENO_VALUE_FLAGS = ("-c", "--config")
# Package runner flags that take the next word as their value.
PACKAGE_RUNNER_VALUE_FLAGS = ("-p", "--package")
# A call that writes, deletes, moves or truncates a file, or runs a child process (the `whole` group, whose text is its
# own target). An `open(` is a write only when write_target_text finds a write mode.
FILE_WRITE = re.compile(r"""\bopen\s*\(?\s*(?:my\s+)?[$\w]+\s*,\s*['"]\+?>|\bopen\s*\("""
                        r"""|\.write_(?:text|bytes)\s*\("""
                        r"""|\b(?:writeFileSync|writeFile|appendFileSync|appendFile|createWriteStream)\s*\("""
                        r"""|\bDeno\.write(?:Text)?File(?:Sync)?\s*\(|\bBun\.write\s*\(|\b(?:File|IO)\.write\b"""
                        r"""|\bshutil\.(?:copy\w*|move|rmtree)\s*\("""
                        r"""|\bos\.(?:replace|rename|remove|unlink|rmdir|truncate)\s*\("""
                        r"""|\bFile\.(?:delete|unlink|rename)\b|\bFileUtils\.\w+|\b(?:unlink|rename)\b(?=\s*[($@'"])"""
                        r"""|\.(?:unlink|touch|truncate|rename|rmdir|rm|copyFile)(?:Sync)?\s*\(|\.replace\s*\("""
                        r"""|(?P<whole>\bfileinput\.input\s*\([^)]*inplace\s*=\s*True|\bsubprocess\.\w+"""
                        r"""|\bos\.(?:system|popen)\b|\b(?:execSync|spawnSync|exec|spawn|execFile\w*)\s*\(|\bsystem\b(?=\s*[('"])"""
                        r"""|`)""")
# A write whose target is its call's last argument: a `shutil` copy, a ruby `FileUtils.cp`, or perl's
# `open(my $f, '>', $path)`. A move or rename changes its source too, so all its arguments are targets.
LAST_ARGUMENT_WRITE = re.compile(r"""\bshutil\.copy|\bFileUtils\.cp\b"""
                                 r"""|\bopen\s*\(?\s*(?:my\s+)?[$\w]+\s*,\s*['"]\+?>""")
# A node copy, whose target is its second argument: a callback or a mode may follow it.
SECOND_ARGUMENT_WRITE = re.compile(r"\.copyFile")
# The head of a call written with parentheses: its name, then the open parenthesis.
CALL_HEAD = re.compile(r"[\w.]*\s*\(")
# A keyword argument (`ignore_errors=True`).
KEYWORD_ARGUMENT = re.compile(r"\s*\w+\s*=(?!=)")
# A write whose first argument is the path and whose later arguments are content or options.
FIRST_ARGUMENT_WRITE = re.compile(r"(?:writeFile|appendFile|createWriteStream|(?:Bun|Deno|File|IO)\.write)")
# The mode argument of an `open` that writes: a literal, or (for `open(path, mode)`) a name that may hold one.
WRITE_MODE = re.compile(r"""['"][rbt]*[wax+][rbt+]*['"]""")
NAMED_MODE = re.compile(r"\s*(?:mode\s*=\s*)?[A-Za-z_][\w.:]*\s*$")
# The interpreter families in which a backtick span runs a command.
BACKTICK_FAMILIES = ("perl", "ruby")
# Programs a child process runs that write the file they name; sed, perl and awk write only in place.
WRITER_PROGRAMS = ("tee", "cp", "mv", "rm", "install")
FUNCTION_DEFINITION = re.compile(r"\b(?:def|function)\s+(\w+)\s*\(([^)]*)\)")
# A name the code uses, not an attribute after a `.`.
CODE_NAME = re.compile(r"(?<![\w.$])\$?[A-Za-z_]\w*")
MAX_NAME_HOPS = 4
# Text through which a write target reads the command line: argv itself, perl's `shift`, an argument parser's
# result, or fileinput's in-place mode, which rewrites the files argv names.
ARGV_SOURCE = re.compile(r"\b(\w*argv|ARGV|ARGF|shift|opts|docopt|parse_args|parse_known_args|parseArgs)\b"
                         r"|\bDeno\.args\b|\bfileinput\b|\$\*")
# A perl file test (`-e "x"`), whose letter is no variable.
PERL_FILE_TEST = re.compile(r"(?<!\S)-[a-zA-Z](?=\s|$)")
# A newline after a comma or an opening bracket: it continues an argument list.
ARGUMENT_LIST_NEWLINE = re.compile(r"([,\[(])[ \t]*\n")
# The `args=` keyword of a child process call.
KEYWORD_ARGS = re.compile(r"(?<![\w.])args\s*=(?!=)")
# Names a language supplies; one the code binds is traced like any other name.
LANGUAGE_NAMES = frozenset(("true", "false", "null", "undefined", "nil", "process",
                            "__file__", "__dirname", "if", "else", "not", "and", "or", "in", "is", "lambda",
                            "await", "new", "my", "die", "unless", "__dir__", "__FILE__", "__filename", "$ENV"))
# A name and what follows it: a call, an attribute, a scope, or a keyword argument or option key (`ok=`, `ok:`).
NAME_USE = re.compile(r"(?<![\w.$])(\$?[A-Za-z_]\w*)(\s*\(|\s*\.|\s*::|\s*->|\s*=(?!=)|\s*:(?!:))?")
# What may stand before a keyword argument or option key.
KEY_PRECEDERS = ("(", "{", ",")
# The call heads that return their argument's path, changed in form: the trace follows their arguments.
PATH_FUNCTIONS = frozenset(("str", "String", "Path", "PurePath", "Pathname", "abspath", "realpath", "normpath",
                            "expanduser", "expandvars", "expand_path", "join", "resolve", "fspath", "format",
                            "absolute", "strip", "rstrip", "lstrip", "joinpath", "as_posix"))
CALL_RESULT = re.compile(r"\s*(?:new\s+|await\s+)?([A-Za-z_][\w.]*)\s*\(.*\)\s*$", re.S)
# The call heads that make a root off the cwd: the home folder or a new temp folder.
NEW_ROOT_FUNCTIONS = frozenset(("home", "gettempdir", "mkdtemp", "TemporaryDirectory"))
# The call heads that return the cwd.
CWD_FUNCTIONS = frozenset(("cwd", "getcwd", "getcwdb", "pwd"))
# The call heads that join their later arguments onto their first (`os.path.join(B, 'a')`, `Path(B, 'a')`).
JOIN_FUNCTIONS = frozenset(("join", "Path", "PurePath"))
# The value a text opens with: a name, dotted or not, and the `(` of a call when one follows. A name glued to a quote
# is a string prefix (`f"..."`), not a value.
LEADING_VALUE = re.compile(r"""[\s(]*(?:new\s+|await\s+)?(\$?[A-Za-z_][\w.$]*)(?![\w.$'"])\s*(\()?""")
# What may follow a call before a join operator: attributes and empty calls (`Path(x).parent`, `.resolve()`).
CALL_TAIL = re.compile(r"(?:\s*\.\s*\w+(?:\s*\(\s*\))?)*")
JOIN_OPERATOR = re.compile(r"\s*\)?\s*[/+]")
RETURN_VALUE = re.compile(r"\breturn\b[ \t]*([^\n;]*)")
# An assignment that unpacks into two or more names: (targets, right side).
UNPACKING = re.compile(r"^[ \t]*(?:(?:const|let|var|my)\s+)?([\[(]?[\w$*]+(?:[ \t]*,[ \t]*[\w$*]+)+[\])]?)[ \t]*"
                       r"=(?![=>])[ \t]*([^\n]+)", re.M)
MAX_BASE_HOPS = 8
# The other names a for loop's target list may hold beside the traced one (`for path, old, new in EDITS`).
LOOP_TARGETS = r"[\w\s,()\[\]]*?"
MAX_SCRIPT_BYTES = 1_000_000
# A call that lists files: python glob and Path listings, os walks and listings, node readdir, ruby Dir, perl glob.
LISTING_CALL = re.compile(r"\b(?:i?glob|rglob|iterdir|walk|listdir|scandir|readdirSync|readdir)\s*\("
                          r"|\bDir\s*(?:\.(?:glob|entries|children|each_child|foreach|new|open)\b|\[)")
# A python call that runs a program that lists files (`git ls-files`, `git grep -l`, `find`, `ls`).
LISTING_COMMAND_CALL = re.compile(r"\b(?:subprocess\.(?:run|check_output|Popen)|os\.popen)\s*\("
                                  r"[^)]*?(?<![\w-])(?:ls-files|grep|find|ls)(?![\w-])")
# A ruby block's parameters (`|f|`), a node callback's parameters (`n =>`, `(a, b) =>`, `function (n)`), and the
# variable of a perl loop.
BLOCK_PARAMETERS = re.compile(r"\|([\w\s,]+)\||(\w+)\s*=>|\(([\w\s,]+)\)\s*=>|function\s*\(([\w\s,]*)\)")
PERL_LOOP_VARIABLE = re.compile(r"\bfor(?:each)?\s+(?:my\s+|our\s+)?(\$\w+)")
# The script's own path in python's argv (`sys.argv[0]`), no argument. Node's `process.argv[0]` is the node binary;
# its script path `process.argv[1]` stays an argv source.
SCRIPT_ARGV = re.compile(r"\b(?:sys\.)?argv\[0\]")
# A call that makes a temp folder or names the temp root; the NEW_ROOT_FUNCTIONS, their node and file forms,
# and ruby's Dir.tmpdir and Dir.mktmpdir.
TEMP_BASE_CALL = re.compile(r"\b(?:" + "|".join(sorted(NEW_ROOT_FUNCTIONS - {"home"}))
                            + r"|mkdtemp\w*|tmpdir)\s*\(|\bDir\.(?:tmpdir|mktmpdir)\b")


# The code an interpreter step runs, the arguments passed to it, and its family name.
InterpreterCode = namedtuple("InterpreterCode", "code arguments family")
# What scan_interpreter_arguments found: the code when no script file is run, else the script word and the arguments
# after it.
ArgumentScan = namedtuple("ArgumentScan", "code script_word rest")


def peel_package_runner(words):
    """The words after an `npx` or `pnpm exec` call and its flags, so the program it runs is the command word."""
    if not words:
        return words

    name = os.path.basename(words[0])
    if name == "npx":
        rest = words[1:]
    elif name == "pnpm" and words[1:2] == ["exec"]:
        rest = words[2:]
    else:
        return words

    while rest and rest[0].startswith("-"):
        takes_value = rest[0] in PACKAGE_RUNNER_VALUE_FLAGS
        rest = rest[2:] if takes_value else rest[1:]
    return rest


def program_family(program):
    """The family name ("python", "node", "ruby" or "perl") of an interpreter program."""
    for pattern, family in PROGRAM_FAMILIES:
        if pattern.fullmatch(program):
            return family
    return None


def interpreter_code(segment, cwd, written_paths, command):
    """(code, arguments, family name) an interpreter step runs: the `-c`/`-e` code, or the text of an untracked script
    file. A script the same command writes first (`cat > x.py <<EOF ... && python3 x.py`) does not exist yet, so its
    code is the whole command, heredoc bodies included. None for any other step, a module run, or a git-tracked or
    git-ignored script: tracked code is reviewed, and an ignored file is a build output or dependency rather than an
    ad hoc edit."""
    words = shell_command.command_after_wrappers(shell_command.segment_words(segment), peel_containers=False)
    words = peel_package_runner(words)
    if not words or not INTERPRETER.fullmatch(os.path.basename(words[0])):
        return None

    program = os.path.basename(words[0])
    family_name = program_family(program)
    family = shell_command.INTERPRETER_FAMILIES[family_name]
    arguments = words[1:]
    if program == "deno" and arguments[:1] == ["eval"]:
        return deno_eval_code(arguments[1:], family_name)
    if program in ("deno", "bun") and arguments[:1] == ["run"]:
        arguments = arguments[1:]

    scan = scan_interpreter_arguments(program, family, family_name, arguments)
    if scan.script_word is None:
        return scan.code

    script = resolve_target(scan.script_word, cwd)
    if script in written_paths:
        return InterpreterCode(command, scan.rest, family_name)
    script_text = untracked_script_text(script)
    if script_text is None:
        return None
    return InterpreterCode(script_text, scan.rest, family_name)


def deno_eval_code(arguments, family_name):
    """The code of a `deno eval` call, whose flags come before it; None when it has none."""
    code_arguments = arguments
    while code_arguments and code_arguments[0].startswith("-"):
        code_arguments = code_arguments[1:]
    if not code_arguments:
        return None
    return InterpreterCode(code_arguments[0], code_arguments[1:], family_name)


def inline_code_after(arguments, index, family_name):
    """The inline code at arguments[index], with the arguments after it; None when the flag ends the line."""
    if index >= len(arguments):
        return None
    return InterpreterCode(arguments[index], arguments[index + 1:], family_name)


def scan_interpreter_arguments(program, family, family_name, arguments):
    """Walk an interpreter's arguments to the first thing that settles what code it runs: inline code or a flag that
    reads none (the `code` field, set with `script_word` None), or the script file word and the arguments after it."""
    value_options = set(family["value_options"])
    if program == "deno":
        value_options.update(DENO_VALUE_FLAGS)
    index = 0
    while index < len(arguments):
        word = arguments[index]
        index += 1
        if shell_command.is_inline_code_option(word, family):
            attached = shell_command.attached_inline_code(word, family)
            if attached:
                return ArgumentScan(InterpreterCode(attached, arguments[index:], family_name), None, None)
            return ArgumentScan(inline_code_after(arguments, index, family_name), None, None)
        if word in family["no_stdin_code_flags"]:
            return ArgumentScan(None, None, None)
        if word in value_options:
            index += 1
            continue
        if word.startswith("-"):
            continue
        return ArgumentScan(None, word, arguments[index:])
    return ArgumentScan(None, None, None)


def untracked_script_text(script):
    """The text of a script file that exists, is no larger than MAX_SCRIPT_BYTES and is neither git-tracked nor
    git-ignored; None for any other path (None included) or a file that cannot be read."""
    if script is None or not os.path.isfile(script):
        return None
    if is_git_tracked(script) or script_utils.is_git_ignored(script):
        return None
    try:
        if os.path.getsize(script) > MAX_SCRIPT_BYTES:
            return None
        with open(script, encoding="utf-8", errors="replace") as script_file:
            return script_file.read()
    except OSError:
        return None


def write_statements(code, family, include_method_replace=True):
    """(statement, target) for each file write in code of the interpreter family ("python", "node", "ruby" or "perl").
    The statement is the `;`-separated part of the write's line, extended through the close of any bracket the write
    opens, so a tracked file the code only reads elsewhere does not count. The target is the part of it that names the
    written file. A backtick runs a command only in perl and ruby. A `.replace(` is a string method as often as a path
    move; include_method_replace False leaves it out."""
    writes = []
    for match in FILE_WRITE.finditer(code):
        if match.group(0) == "`" and family not in BACKTICK_FAMILIES:
            continue
        if match.group(0).startswith(".replace") and not include_method_replace:
            continue

        statement, statement_start = statement_around(code, match)
        whole_call = bool(match.group("whole"))
        target = write_target_text(statement, match.start() - statement_start, whole_call)
        if target is not None:
            writes.append((statement, target))
    return writes


def runs_editor(call):
    """Whether a child process call's text names a program that writes a file: `tee`, `cp`, `mv`, `rm`, `install`,
    or `sed -i`, `perl -pi` and `awk -i inplace`. Quotes, commas and brackets are read as spaces, so an argument list
    (`['sed', '-i', ...]`) reads like a command line. A program counts only in program position: the word after the
    call's name (the first word of a backtick span), or the word after a shell separator (`;`, `&&`, `||`, `|`, a lone
    `&`, or a newline) or an `args=` keyword. A newline after a comma or an opening bracket continues an argument
    list and is no separator, except inside a string, where a newline always separates shell lines."""
    call = sub_outside_strings(ARGUMENT_LIST_NEWLINE, r"\1 ", call)
    call = sub_outside_strings(KEYWORD_ARGS, " ; ", STRING_PREFIX_BEFORE_QUOTE.sub("", call))
    command_line = re.sub(r"""[\[\](){}'",`]""", " ", call)
    steps = [step for _operator, step in shell_command.split_command_steps(command_line)]
    for step_index, step in enumerate(steps):
        words = shell_command.words_by_blank(step)
        program_index = 0 if step_index > 0 or call.startswith("`") else 1
        if program_index >= len(words):
            continue

        program = words[program_index].rsplit("/", 1)[-1]
        arguments_text = " ".join(words[program_index + 1:])
        if program in WRITER_PROGRAMS or is_inplace(program, arguments_text):
            return True
    return False


def last_argument_target(arguments):
    """The target text of a write whose path is its last positional argument, plus its keyword arguments' values."""
    # A trailing comma leaves an empty last part. A keyword argument is an option, but its value still counts.
    filled_arguments = [argument for argument in arguments if trim(argument)]
    keyword_arguments = [argument for argument in filled_arguments if KEYWORD_ARGUMENT.match(argument)]
    positional_arguments = [argument for argument in filled_arguments if argument not in keyword_arguments]
    return ",".join(positional_arguments[-1:] + keyword_arguments)


def write_target_text(statement, write_start, whole_call):
    """The text that names what a write call writes, or None for a call that writes nothing: an `open` with no write
    mode, a `str.replace`, or a child process that runs no editor. The target is the call itself for a child process
    and fileinput's in-place mode; the receiver of `.write_text(`; the receiver and first argument of a method `.open(`;
    the receiver and arguments of a method that moves or deletes; the last argument of a `shutil` copy or perl open;
    the first argument of a call that writes content; else all the arguments (a delete, move or rename)."""
    call = statement[write_start:]
    if whole_call:
        return call if call.startswith("fileinput") or runs_editor(call) else None

    if statement.startswith(".write_", write_start):
        return receiver_text(statement[:write_start])

    # A call with no parenthesis after its name (`unlink $x or die(...)`) has its arguments up to the end of the line,
    # whatever parenthesis follows.
    call_head = CALL_HEAD.match(call)
    if call_head is None:
        write_word = call.split(None, 1)[0]
        arguments_start = write_start + len(write_word)
    else:
        arguments_start = write_start + call_head.end()
    arguments = split_arguments(statement, arguments_start, multiline=call_head is not None)
    if LAST_ARGUMENT_WRITE.match(statement, write_start):
        return last_argument_target(arguments)
    if SECOND_ARGUMENT_WRITE.match(statement, write_start):
        return arguments[1] if len(arguments) > 1 else ",".join(arguments)
    if statement.startswith(".", write_start):
        if call.startswith(".replace") and len(arguments) != 1:
            return None
        return receiver_text(statement[:write_start]) + "," + ",".join(arguments)
    if statement.startswith("open", write_start):
        return open_target(statement, write_start, arguments)
    if FIRST_ARGUMENT_WRITE.match(statement, write_start):
        return arguments[0]
    return ",".join(arguments)


def open_target(statement, write_start, arguments):
    """The target text of an `open` call, or None when it has no write mode."""
    is_method = statement[write_start - 1:write_start] == "."
    modes = arguments if is_method else arguments[1:]
    if not any(WRITE_MODE.search(mode) or (not is_method and NAMED_MODE.match(mode)) for mode in modes):
        return None

    # `p.open('w')` writes its receiver; `io.open(path, 'w')` and `codecs.open(...)` write their first argument.
    return receiver_text(statement[:write_start - 1]) + "," + arguments[0] if is_method else arguments[0]


def binding_texts(code, name):
    """The text that binds `name`: an assignment's right side, a for loop's iterable (the element at the name's
    position in a multi-name target), and for a function parameter, the argument at its position in each call."""
    word = re.escape(name.lstrip("$"))
    texts = assigned_texts(code, word)
    texts += loop_binding_texts(code, name, word)
    texts += parameter_binding_texts(code, word)
    return texts


def loop_matches(code, word):
    """Each for loop whose target list holds the name `word` (regex-escaped)."""
    loop = re.compile(rf"\bfor\s*\(?\s*(?:(?:const|let|var|my)\s+)?(?P<targets>{LOOP_TARGETS}\b{word}\b{LOOP_TARGETS})"
                      r"\s(?:in|of)\s")
    return list(loop.finditer(code))


def loop_binding_texts(code, name, word):
    """The iterable of each for loop whose target list holds `name` (`word` is its regex-escaped form)."""
    texts = []
    for match in loop_matches(code, word):
        texts += one_loop_texts(code, name, match)
    return texts


def loop_iterable_texts(code, texts):
    """The whole iterable of each for loop whose target list holds a name used in texts, so a listing call in a
    multi-name loop (`for a, b in os.walk(...)`) stays visible beside the per-position fields the trace follows."""
    names = {name.lstrip("$") for text in texts for name in CODE_NAME.findall(text)}
    iterables = []
    for name in sorted(names):
        for match in loop_matches(code, re.escape(name)):
            iterables.append(",".join(split_arguments(code, match.end())))
    return iterables


def one_loop_texts(code, name, match):
    """The text a for loop binds to `name`: its whole iterable, or the element at the name's position in a
    multi-name target."""
    iterable_start = match.end()
    iterable = ",".join(split_arguments(code, iterable_start))
    targets = [target.strip(" \t\n()[]$") for target in match.group("targets").split(",")]
    bare_name = name.lstrip("$")
    position = targets.index(bare_name) if bare_name in targets else None
    if len(targets) == 1 or position is None:
        return [iterable]
    if iterable.lstrip().startswith("zip("):
        zip_arguments = split_arguments(iterable, iterable.index("(") + 1)
        if position < len(zip_arguments):
            return [zip_arguments[position]]
        return [iterable]
    iterable_name = trim(iterable).rstrip(":{").strip(SP).removesuffix(".items()")
    sources = assigned_texts(code, re.escape(iterable_name)) if iterable_name.isidentifier() else []
    fields = []
    for source in sources or [iterable]:
        fields += tuple_fields(source, position)
    return [field for field in fields if field.strip()] or [iterable]


def parameter_binding_texts(code, word):
    """The argument at the parameter's position in each call of each function that has a parameter named `word`
    (regex-escaped)."""
    parameter = re.compile(rf"(?<![\w$]){word}\b")
    texts = []
    for function in FUNCTION_DEFINITION.finditer(code):
        parameters = [part.strip(SP) for part in function.group(2).split(",")]
        positions = [index for index, part in enumerate(parameters) if parameter.match(part)]
        if not positions:
            continue
        texts += call_argument_texts(code, function, positions[0])
    return texts


def call_argument_texts(code, function, position):
    """The argument at `position` in each call of a function the code defines (`function` is its definition match)."""
    function_name = re.escape(function.group(1))
    call_pattern = rf"(?<![\w.]){function_name}\s*\("
    texts = []
    for call in re.finditer(call_pattern, code):
        if call.start() == function.start(1):
            continue
        arguments = split_arguments(code, call.end(), multiline=True)
        if position < len(arguments) and trim(arguments[position]):
            texts.append(arguments[position])
    return texts


def assigned_texts(code, word):
    """The right side of each assignment, augmented assignment and unpacking (`src, dst = ...`, `my ($out) = ...`,
    `const [, out] = ...`) included, to the (regex-escaped) name `word`."""
    assignment = re.compile(rf"(?:^|[;{{:])[ \t]*(?:(?:const|let|var|my|our)\s+)?[\[(]?\s*(?:[\w$*.]*\s*,\s*)*"
                            rf"\*?\$?{word}\s*(?::[^=\n]*)?(?:\s*,\s*[\w$*.]*)*\s*[\])]?\s*[-+*/%|&^]*=(?![=>])", re.M)
    texts = []
    for match in assignment.finditer(code):
        right_side = split_arguments(code, match.end())
        texts.append(",".join(right_side))
    return texts


def named_texts(code, text):
    """`text` plus the text that binds each name it uses, followed through MAX_NAME_HOPS bindings."""
    texts = [text]
    frontier = [text]
    seen = set()
    for _hop in range(MAX_NAME_HOPS):
        names = set()
        for part in frontier:
            names.update(CODE_NAME.findall(part))
        names -= seen
        seen |= names
        frontier = []
        for name in sorted(names):
            frontier += binding_texts(code, name)
        texts += frontier
    return texts


def writes_reach_argv(code, family):
    """Whether any write's target can come from the command line, so a tracked file passed as an argument may be the
    file written. A name that no assignment, loop or call argument binds counts as reaching argv (an unpacking of a
    parsed result, a callback parameter, a name the code does not set), except a name the code imports or the
    language supplies, and a capitalized name (`open(OUT, 'w')`), read as a class or module. Each name is traced
    once across all the writes."""
    supplied_names = imported_names(code) | LANGUAGE_NAMES
    traced = {}
    targets = [target for _statement, target in write_statements(code, family)]
    return any(text_reaches_argv(code, target, traced, supplied_names) for target in targets)


def text_reaches_argv(code, text, traced, supplied_names):
    """Whether `text` names argv or a name that reaches it. A string literal counts only for what it interpolates; the
    name before a call is a function, a name before `=` or `:` after a `(`, `{` or `,` is a keyword argument or option
    key, and a capitalized name that nothing binds is a class or module (`File.join`, `File.open`), not a variable."""
    text = PERL_FILE_TEST.sub(" ", code_outside_strings(text))
    if ARGV_SOURCE.search(text):
        return True

    for found in NAME_USE.finditer(text):
        name = found.group(1)
        follower = (found.group(2) or "").strip()
        before = text[:found.start(1)].rstrip()[-1:]
        if follower == "(" or (follower in ("=", ":") and before in KEY_PRECEDERS):
            continue
        if name[0].isupper() and name not in traced and not binding_texts(code, name):
            traced[name] = False
        if name_reaches_argv(code, name, traced, supplied_names):
            return True
    return False


def name_reaches_argv(code, name, traced, supplied_names):
    """Whether `name`, traced through the text that binds it, reaches argv; traced holds each name's answer. A name
    bound through itself adds nothing. The result of a call to a function that is not a PATH_FUNCTIONS member is a new
    value: only argv written in the call itself reaches it."""
    if name in traced:
        return traced[name]

    traced[name] = False
    bindings = binding_texts(code, name)
    unbound = not bindings and name not in supplied_names
    traced[name] = unbound or any(binding_reaches_argv(code, text, traced, supplied_names) for text in bindings)
    return traced[name]


def binding_reaches_argv(code, text, traced, supplied_names):
    call = CALL_RESULT.fullmatch(text)
    if call and call.group(1).rsplit(".", 1)[-1] not in PATH_FUNCTIONS:
        argument_code = code_outside_strings(text)
        return bool(ARGV_SOURCE.search(argument_code))

    return text_reaches_argv(code, text, traced, supplied_names)


def path_candidates(text):
    """Each string literal in text, and all of them joined with `/` (`ROOT / "docs" / "a.md"`)."""
    literals = literals_in(text)
    joined = ["/".join(literals)] if len(literals) > 1 else []
    return literals + joined


def literals_in(text):
    """The contents of each string literal in text."""
    return [match.group(2) for match in STRING_LITERAL.finditer(text)]


def absolute_root(code, target):
    """The absolute folder a write target joins onto (`R / 'a'`, `T + f`, `os.path.join(R, 'a')`), else None. The
    root is the target's first name that is not called or followed by a `.`, followed by a join operator, and whose
    every binding (an assignment, an augmented assignment, a loop or a call argument) is only one string
    literal (a call head or attribute may surround it, no other name), an absolute path, the same one in all of
    them. A name bound to different paths, to a relative one, or to a join with another name is no root. The name
    scan does not skip quoted text, so a target whose first name sits inside a leading string literal
    (`Path('/tmp/x') / 'a'`, `'/tmp/x/' + R`, `'sub/' + R`) has no root."""
    for match in CODE_NAME.finditer(target):
        if re.match(r"\s*[(.]", target[match.end():]):
            continue
        if not re.match(r"\s*\)?\s*[/+,]", target[match.end():]):
            return None
        bindings = binding_texts(code, match.group())
        literals = [literals_in(text) for text in bindings]
        if not literals or any(len(found) != 1 or not found[0].startswith("/") for found in literals):
            return None
        if len({found[0] for found in literals}) != 1:
            return None
        if any(reads_other_name(text) for text in bindings):
            return None
        return literals[0][0]
    return None


def reads_other_name(text):
    """Whether text, its string literals removed, holds a name that is neither called nor followed by a `.`."""
    rest = STRING_LITERAL.sub("", text)
    return any(not re.match(r"\s*[(.]", rest[name.end():]) for name in CODE_NAME.finditer(rest))


def joined_off_cwd(code, text):
    """Whether text is one value that joins its literals onto a base that cannot be the cwd: the base `B` of
    `B / 'a'`, `B + 'a'`, `join(B, 'a')` or `Path(B, 'a')` opens text, and base_may_be_cwd finds it cannot be. The
    literals then name files under that base, not under the cwd."""
    if split_arguments(text, 0, multiline=True) != [text]:
        return False
    leading = LEADING_VALUE.match(text)
    if leading is None:
        return False

    base_end = leading.end()
    if leading.group(2):
        arguments = split_arguments(text, leading.end(), multiline=True)
        if leading.group(1).rsplit(".", 1)[-1] in JOIN_FUNCTIONS and len(arguments) > 1:
            return not base_may_be_cwd(code, arguments[0], frozenset())
        call_close = next((index for index, char in top_level_positions(text, leading.end()) if char in ")]}"),
                          len(text))
        base_end = CALL_TAIL.match(text, call_close + 1).end() if call_close < len(text) else len(text)
    if not JOIN_OPERATOR.match(text, base_end):
        return False
    return not base_may_be_cwd(code, text, frozenset())


def base_may_be_cwd(code, text, seen, position=None):
    """Whether the value text opens with may be the cwd or a folder under it. A string literal, a cwd call, argv, a
    name with no binding and a trace past MAX_BASE_HOPS steps may be. A call in PATH_FUNCTIONS is its first argument; a
    call in NEW_ROOT_FUNCTIONS makes a root off the cwd; a call to a function the code defines is what it returns;
    any other call, and a function with no return found, may be. A name may be when any binding may be; a binding
    through itself adds nothing. position is the part of a returned tuple a name is unpacked from."""
    leading = LEADING_VALUE.match(text)
    if leading is None:
        return True
    name = leading.group(1)
    head = name.rsplit(".", 1)[-1]
    if head in CWD_FUNCTIONS or ARGV_SOURCE.search(name):
        return True

    key = name + "()" if leading.group(2) else name
    if key in seen:
        return False
    if len(seen) >= MAX_BASE_HOPS:
        return True
    seen = seen | {key}

    if leading.group(2):
        if head in PATH_FUNCTIONS:
            arguments = [argument for argument in split_arguments(text, leading.end(), multiline=True)
                         if trim(argument)]
            return not arguments or base_may_be_cwd(code, arguments[0], seen)
        returned = returned_texts(code, head, position)
        if not returned and head in NEW_ROOT_FUNCTIONS and not defines_function(code, head):
            return False
        return not returned or any(base_may_be_cwd(code, value, seen) for value in returned)

    bindings = binding_texts(code, name)
    return not bindings or any(base_may_be_cwd(code, binding, seen, unpacked_position(code, name, binding))
                               for binding in bindings)


def unpacked_position(code, name, binding):
    """The position of name among the targets of an unpacking (`tree, sha = build()`) whose right side is binding,
    else None."""
    for unpacking in UNPACKING.finditer(code):
        targets = [target.strip(SP + "()[]$*") for target in unpacking.group(1).split(",")]
        if name.lstrip("$") in targets and trim(unpacking.group(2)).startswith(trim(binding)):
            return targets.index(name.lstrip("$"))
    return None


def defines_function(code, function_name):
    """Whether the code binds this name: a function definition, an assignment (a lambda or an alias), or an import
    alias."""
    if any(definition.group(1) == function_name for definition in FUNCTION_DEFINITION.finditer(code)):
        return True
    if re.search(rf"\bimport\b[^\n]*\bas\s+{re.escape(function_name)}\b", code):
        return True
    return bool(binding_texts(code, function_name))


def returned_texts(code, function_name, position=None):
    """Each value a function the code defines returns, a returned tuple split into its parts, or only the part at
    position when the tuple has one there. A function's body runs to the next function definition. Empty for a
    function the code does not define."""
    definitions = list(FUNCTION_DEFINITION.finditer(code))
    values = []
    for index, definition in enumerate(definitions):
        if definition.group(1) != function_name:
            continue
        body_end = definitions[index + 1].start() if index + 1 < len(definitions) else len(code)
        for returned in RETURN_VALUE.finditer(code, definition.end(), body_end):
            parts = [part for part in split_arguments(returned.group(1), 0) if trim(part)]
            values += parts[position:position + 1] if position is not None and position < len(parts) else parts
    return values


def written_candidates(code, family):
    """The path texts code's file writes name: each literal in a write statement, and each literal its target is
    bound to. When a write's target joins onto an absolute_root, the target's own literals and the names it reads are
    joined onto that root; other literals of the statement stay relative. A text joined_off_cwd names no candidate."""
    candidates = []
    for statement, target in write_statements(code, family):
        root = absolute_root(code, target)
        if root is None:
            candidates += candidates_off_root(code, statement, target)
        else:
            candidates += candidates_on_root(code, statement, target, root)
    return candidates


def candidates_off_root(code, statement, target):
    """The path texts of one write whose target joins onto no absolute root."""
    literals = literals_in(statement)
    own = literals_in(target)
    if joined_off_cwd(code, target):
        literals = list((Counter(literals) - Counter(own)).elements())
    named = []
    for text in named_texts(code, target):
        if joined_off_cwd(code, text):
            continue
        named += path_candidates(text)
    return literals + named


def candidates_on_root(code, statement, target, root):
    """The path texts of one write whose target joins onto an absolute root: its own literals and the names it reads
    are joined onto the root; the other literals of the statement stay relative."""
    literals = literals_in(statement)
    own = literals_in(target)
    named = []
    for text in named_texts(code, target):
        named += path_candidates(text)
    other = list((Counter(literals) - Counter(own)).elements())
    return other + [literal if literal.startswith("/") else root.rstrip("/") + "/" + literal
                    for literal in own + named]


def interpreter_written_target(found, folders):
    """(raw path, path) of the git-tracked file an interpreter step opens for writing, else None: code with a file
    write whose statement names a tracked file as a string literal, whose target is a name bound (through
    assignments, for loops and function calls) to a tracked file's literal or to literals that join into one, or a
    tracked file passed as an argument unless the trace finds that no write target comes from argv. folders holds the
    session cwd, then each literal cd folder before the step, and a relative path counts when it names a tracked
    file under any of them. A path the code builds any other way is not seen. found is the interpreter_code result
    of the step."""
    if found is None:
        return None

    raw_code, arguments, family = found

    # A bracket or quote inside a comment cuts a literal, and a `#` that starts no comment (a JS regex, perl's
    # `s/a #b/`) cuts real code, so trace the code both with and without comments.
    codes = dict.fromkeys((raw_code, without_comments(raw_code)))
    if not any(write_statements(code, family) for code in codes):
        return None

    candidates = []
    for code in codes:
        candidates += written_candidates(code, family)

    # A tracked file passed to code whose writes all name files of their own is read, not written.
    if arguments and any(writes_reach_argv(code, family) for code in codes):
        candidates += arguments
    for candidate in candidates:
        tracked_path = tracked_candidate_path(candidate, folders)
        if tracked_path:
            return candidate, tracked_path
    return None


def argv_is_all_temp(arguments, cwd):
    """Whether the step has arguments and every one is a path under a temp dir."""
    if not arguments:
        return False
    for argument in arguments:
        argument_path = resolve_target(argument, cwd)
        if argument_path is None or not is_under_temp_dir(argument_path):
            return False
    return True


def names_temp_base(texts):
    """Whether any text makes a temp folder (a NEW_ROOT_FUNCTIONS-style call that returns one) or holds an absolute
    literal path under a temp dir."""
    for text in texts:
        if TEMP_BASE_CALL.search(code_outside_strings(text)):
            return True
        for literal in literals_in(text):
            if literal.startswith("/") and is_under_temp_dir(literal):
                return True
    return False


def names_bound_by_listing(code, family):
    """The names a perl loop variable, a ruby block parameter or a node callback parameter takes from a listing call
    on the same line (`for my $f (glob(...))`, `Dir.glob(...).each do |f|`, `fs.readdirSync(...).forEach(n => ...)`).
    The `|f|` form counts only for ruby: elsewhere `|` is a regex alternation. The arrow and `function (...)` forms
    count only for node: in perl and ruby `=>` pairs a hash key. The trace binds
    python loop names and node `for ... of` names itself."""
    names = set()
    for line in code.splitlines():
        if not LISTING_CALL.search(code_outside_strings(line)):
            continue
        for groups in BLOCK_PARAMETERS.findall(line):
            block_group = groups[0] if family == "ruby" else ""
            callback_groups = groups[1:] if family == "node" else ()
            parameters = ",".join((block_group, *callback_groups))
            names.update(name.strip().lstrip("$") for name in parameters.split(",") if name.strip())
        names.update(match.lstrip("$") for match in PERL_LOOP_VARIABLE.findall(line))
    return names


def reads_listing_name(texts, listing_names):
    """Whether any text uses a name in listing_names."""
    return any(name.lstrip("$") in listing_names for text in texts for name in CODE_NAME.findall(text))


def computed_write_source(code, writes, family, arguments, cwd):
    """What a write target of the code is computed from ("a glob or directory listing" or "argv"), else None. Each
    write's target is traced through the names that bind it, so a loop over a listing counts, a listing program run
    through subprocess or os.popen (`git ls-files`, `find`, `ls`, `grep`) included. A write whose traced
    text holds a temp base is proven temp; an argv-sourced write is proven only when every argument is a temp path.
    A name that nothing binds is no source: only a listing or argv the trace reaches counts. Python's `sys.argv[0]` is
    the script's own path, read as `__file__`; node's `process.argv[1]` still counts as argv.
    `code` has SCRIPT_ARGV replaced already, and `writes` is its
    write_statements(code, family, include_method_replace=False)."""
    listing_names = names_bound_by_listing(code, family)
    for _statement, target in writes:
        texts = named_texts(code, target)
        if names_temp_base(texts):
            continue
        code_only = [code_outside_strings(text) for text in texts]
        listing_texts = texts + loop_iterable_texts(code, texts)
        # A listing program's name is a string literal, so the raw text is read.
        if any(LISTING_COMMAND_CALL.search(text) for text in listing_texts):
            return "a glob or directory listing"
        listing_code = [code_outside_strings(text) for text in listing_texts]
        if any(LISTING_CALL.search(text) for text in listing_code) or reads_listing_name(code_only, listing_names):
            return "a glob or directory listing"
        reaches_argv = any(ARGV_SOURCE.search(text) for text in code_only)
        if reaches_argv and not argv_is_all_temp(arguments, cwd):
            return "argv"
    return None


def computed_write_target(found, cwd):
    """What the file write of an interpreter step computes its target from (see computed_write_source), else None.
    found is the interpreter_code result of the step: inline code or an untracked script file."""
    if found is None:
        return None

    raw_code, arguments, family = found
    # A comment's bracket or quote cuts a literal and makes a bound name read as unbound, so the code is read without
    # its comments; the raw text is used only when that leaves no write (a `#` that starts no comment cut the code).
    code = SCRIPT_ARGV.sub("__file__", without_comments(raw_code))
    writes = write_statements(code, family, include_method_replace=False)
    if not writes:
        code = SCRIPT_ARGV.sub("__file__", raw_code)
        writes = write_statements(code, family, include_method_replace=False)
    return computed_write_source(code, writes, family, arguments, cwd)


def tracked_candidate_path(candidate, folders):
    """The git-tracked file a candidate path names under the session cwd (folders[0]) or, when relative, any folder."""
    candidate_folders = [folders[0]] if shell_directory.path_word_is_absolute(candidate) else folders
    for folder in candidate_folders:
        path = resolve_target(candidate, folder)
        path = os.path.normpath(path) if path else path
        if path and os.path.isfile(path) and is_git_tracked(path):
            return path
    return None
