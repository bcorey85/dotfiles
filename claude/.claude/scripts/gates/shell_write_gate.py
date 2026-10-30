#!/usr/bin/env python3
"""PreToolUse hook on Bash: deny shell writes that bypass the Write/Edit hook pipeline.

  1. In-place editors (sed -i, perl -pi, awk -i inplace), any target.
  2. Redirection (>, >>) and tee onto a git-tracked file.
  3. Agent type `coder` (any coder variant, subagent or main session): a redirect or tee that creates a new file
     outside a temp dir, or whose target still holds a `$` after `$TMPDIR` and `$HOME` are expanded; also any
     relative target after any `cd`, `pushd` or `popd`.
  4. An interpreter (python, pypy, node, tsx, ts-node, bun, deno, ruby, perl; also behind npx or pnpm exec) run whose
     inline code (`-c`, `-e`, `-p`, `--print`, `--eval`, `deno eval`) or untracked, not git-ignored script file opens
     a file for writing and names a git-tracked file: as a string literal, through a name bound to one, or as an
     argument.
  5. Any agent: a relative target after a `cd`, `pushd` or `popd` whose folder is not a literal (`cd "$D"`, `popd`,
     `cd -`), because the gate cannot tell where the write lands.
Only a `>` outside quotes is a redirect (a `>` inside a double-quoted `$(...)` is code and is read as one), and the
body of a heredoc is not read as commands unless it feeds a shell interpreter (`bash <<EOF`); the `$(...)` and
backtick spans of an unquoted heredoc body are. A command that names a program running code the parser does not read
(a shell's `-c`, `eval`, `docker exec`, `ssh`; shell_command.CODE_RUNNERS) is also scanned as plain text for `>` and
tee targets, quotes ignored: those targets are checked only against git-tracked files.
A relative target resolves against the session cwd (`cwd` in the hook input) and, for rule 2, also against each
folder a literal `cd` or `pushd` in command position moved to before it, cumulatively; a tracked file under any of
them denies. A relative target after a `cd`, `pushd` or `popd` whose folder is not a literal is denied (rule 5), and
in a coder a relative target after any of them is denied (rule 3).
Escape for rules 1, 2, 4 and 5 in the main session: a trailing `#skip-shell-write-gate` comment. A subagent (agent_id in
the hook input) or a coder cannot use it. Fails closed on internal error.
"""
import json
import os
import re
import shlex
import subprocess
import sys

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import hook_input
import script_utils
import shell_command
from code_text import SP, receiver_text, split_arguments, tuple_fields, without_comments
from hook_input import JqError, expand_env_names, is_under_temp_dir, jq_get, jq_str
from hook_input import bash_basename as shell_basename
from hook_input import bash_dirname as shell_dirname
from shell_statements import strip_comments, strip_heredocs

SPC = r"[ \t\r\f\v]"
TARGET = r"[^ \t\r\f\v|&;<>()]+"
REDIRECT = re.compile(r">[>|&]?" + SPC + "*" + TARGET)
REDIRECT_PREFIX = re.compile(r"^>[>|&]?" + SPC + "*")
TEE = re.compile(r"(^|" + SPC + r")tee(" + SPC + r"+-[a-zA-Z-]+)*" + SPC + "+" + TARGET)
TEE_PREFIX = re.compile(r"^" + SPC + r"*tee(" + SPC + r"+-[a-zA-Z-]+)*" + SPC + "+")
GIT_SUBCOMMANDS = re.compile(r"(rm|mv|checkout|restore|apply)")
SED_INPLACE = re.compile(r"(^|" + SPC + r")(-[a-zA-Z]*i|--in-place(" + SPC + r"|=|$))")
PERL_I = re.compile(r"(^|" + SPC + r")-[a-zA-Z]*i")
PERL_PN = re.compile(r"(^|" + SPC + r")-[a-zA-Z]*[pn]")
AWK_INPLACE = re.compile(r"(^|" + SPC + r")-i" + SPC + "*inplace")
PRECHECK = re.compile(r"(-[a-zA-Z]*i|inplace|>|tee)")
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
FILE_WRITE = re.compile(r"""open\s*\([^)]*['"][rbt]*[wax+][rbt+]*['"]|\.write_(text|bytes)\s*\("""
                        r"""|\b(writeFileSync|writeFile|appendFileSync|appendFile|createWriteStream)\s*\("""
                        r"""|\bDeno\.write(Text)?File(Sync)?\s*\(|\bBun\.write\s*\("""
                        r"""|\b(File|IO)\.write\b|\bshutil\.(copy\w*|move)\s*\(|\bos\.(replace|rename)\s*\("""
                        r"""|\bfileinput\.input\s*\([^)]*inplace\s*=\s*True"""
                        r"""|\bopen\s*\(?\s*(my\s+)?[$\w]+\s*,\s*['"]\+?>""")
STRING_LITERAL = re.compile(r"""(['"])([^'"\n]{1,512})\1""")
# A write whose target is its call's last argument: a copy, move or rename, or perl's `open(my $f, '>', $path)`.
LAST_ARGUMENT_WRITE = re.compile(r"""\bshutil\.|\bos\.|\bopen\s*\(?\s*(my\s+)?[$\w]+\s*,\s*['"]\+?>""")
FUNCTION_DEFINITION = re.compile(r"\b(?:def|function)\s+(\w+)\s*\(([^)]*)\)")
# A name the code uses, not an attribute after a `.`.
CODE_NAME = re.compile(r"(?<![\w.$])\$?[A-Za-z_]\w*")
MAX_NAME_HOPS = 4
# The other names a for loop's target list may hold beside the traced one (`for path, old, new in EDITS`).
LOOP_TARGETS = r"[\w\s,()\[\]]*?"
MAX_SCRIPT_BYTES = 1_000_000
DIRECTORY_COMMANDS = ("cd", "pushd", "popd")
DIRECTORY_COMMAND_TEXT = re.compile(r"(^|[\s;&|(){`])(cd|pushd|popd)(\s|$|[;&|)])")
DIRECTORY_CHANGE_HINT = ("This gate checks a relative path against the session cwd and each cd folder before it; "
                         "use an absolute path for the file you mean.")
ESCAPE_HINT = (" If this deny is wrong (for example a command wrapper this gate does not recognize), re-run the "
               "command with a trailing #skip-shell-write-gate comment — it disarms this gate for that one command.")


class DenyError(Exception):
    pass


def words_of(text):
    return [w for w in re.split("[ \t\n]+", text) if w]


def trim(text):
    return text.strip(SP)


def is_inplace(program, segment):
    if program in ("sed", "gsed"):
        return bool(SED_INPLACE.search(segment))
    if program == "perl":
        return bool(PERL_I.search(segment)) and bool(PERL_PN.search(segment))
    if program in ("awk", "gawk"):
        return bool(AWK_INPLACE.search(segment))
    return False


def find_editor_word(segment):
    # The in-place editor a step runs: its command word once the wrappers are dropped, or an editor named after an
    # invoker (`xargs sed -i`, `find -exec sed -i`, `sh -c`).
    # A docker, podman, kubectl or ssh call runs its editor elsewhere: its wrapper words are not peeled.
    command_words = shell_command.command_after_wrappers(words_of(segment), peel_containers=False)
    invoked = False
    for index, word in enumerate(command_words):
        base = word.rsplit("/", 1)[-1]
        if base in ("sed", "gsed", "perl", "awk", "gawk"):
            if index == 0 or invoked:
                return base
        elif base in ("xargs", "-exec", "-execdir", "sh", "bash", "zsh", "-c", "parallel"):
            invoked = True
    return None


def resolve_target(raw, cwd):
    path = shell_command.path_word(trim(raw))
    if not path or path.startswith("-") or path.startswith("&") or path.startswith("/dev/"):
        return None
    if not path.startswith("/"):
        path = cwd + "/" + path
    return path


def path_word_is_absolute(raw):
    return shell_command.path_word(trim(raw)).startswith("/")


def written_targets(core):
    """Raw target of each redirect and tee a step's command text writes. A `>` inside quotes is no redirect."""
    try:
        commands = shell_command.parse_piped_commands(core)
    except ValueError:
        return regex_written_targets(core, skip_quoted=True)
    targets = []
    for words, redirections, _piped in commands:
        targets += [target for operator, target in redirections
                    if shell_command.redirection_writes_file(operator, target)]
        words = shell_command.command_after_wrappers(words, peel_containers=False)
        if words and os.path.basename(words[0]) == "tee":
            targets += [arg for arg in words[1:] if not arg.startswith("-")]
    return targets


def regex_written_targets(core, skip_quoted):
    """written_targets for text the parser cannot read: the regexes, skipping matches inside quotes when skip_quoted."""
    def matches(pattern):
        return shell_command.unquoted_matches(pattern, core) if skip_quoted else list(pattern.finditer(core))

    targets = []
    for found in matches(REDIRECT):
        operator = REDIRECT_PREFIX.match(found.group(0)).group(0).rstrip(SP)
        target = REDIRECT_PREFIX.sub("", found.group(0))
        if shell_command.redirection_writes_file(operator, target):
            targets.append(target)
    targets += [TEE_PREFIX.sub("", found.group(0)) for found in matches(TEE)]
    return targets


def deny_text(subject, cannot_skip):
    if cannot_skip:
        return (f"[shell-write-gate] {subject} Use the Edit tool for an in-place change, or the Write tool for a new "
                "file. This agent has no way to skip this gate.")
    return f"[shell-write-gate] {subject} Use the Write or Edit tool." + ESCAPE_HINT


def simple_command_texts(step):
    """The text of each simple command in a step, so a command inside a `( )` group or `$( )` is judged on its own.
    A step the parser cannot read is one text: the step without the `(` groups around it."""
    try:
        commands = shell_command.parse_simple_commands(step)
    except ValueError:
        core = trim(shell_command.step_parts(step)[0])
        return [core] if core else []
    texts = []
    for words, _redirections in commands:
        while words and words[0] in shell_command.GROUP_WORDS:
            words = words[1:]
        if words:
            texts.append(shlex.join(words))
    return texts


def directory_changes(step):
    """The folder word of each `cd`, `pushd` or `popd` the step runs, in order, once keywords (`then`, `do`, `!`) and
    wrappers (`command`, `builtin`) are dropped; None for a folder that is not a literal. A step the parser cannot
    read gives one None when the word stands in command position by a text match."""
    try:
        commands = shell_command.parse_piped_commands(step)
    except ValueError:
        return [None] if DIRECTORY_COMMAND_TEXT.search(step) else []
    folders = []
    for words, _redirections, _piped in commands:
        words = shell_command.command_after_wrappers(words)
        if words and words[0] in DIRECTORY_COMMANDS:
            expanded_words = [expand_env_names(word, ("TMPDIR", "HOME")) for word in words]
            folders.append(shell_command.cd_folder(expanded_words))
    return folders


def step_targets(code, cwd):
    """(raw target, folders, unread_change) for every redirect and tee target of the command text, in order. folders
    holds the session cwd, then each folder an earlier step, or the step itself, moved to with a literal `cd` or
    `pushd`, each resolved against the one before. unread_change is True once one moved to a folder that is not a
    literal."""
    targets = []
    folders = [cwd]
    unread_change = False
    for _operator, step in shell_command.split_command_steps(code):
        for folder in directory_changes(step):
            if folder is None:
                unread_change = True
                continue
            folder_path = os.path.join(folders[-1], os.path.expanduser(folder))
            folders = [*folders, os.path.normpath(folder_path)]
        targets += [(raw, folders, unread_change) for raw in written_targets(step)]
    return targets


def code_texts(code):
    """The command text and the text of each `$(...)` and backtick span in it, at any depth: the shell runs the
    spans, also inside double quotes."""
    texts = [code]
    for text in texts:
        texts += shell_command.substitution_spans(text)
    return texts


def git_path_check(path, *git_command):
    try:
        finished = subprocess.run(["git", "-C", shell_dirname(path), *git_command, "--", shell_basename(path)],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return False
    return finished.returncode == 0


def is_git_tracked(path):
    return git_path_check(path, "ls-files", "--error-unmatch")


def run(raw):
    if raw.strip() == "":
        return
    try:
        payload = json.loads(raw)
        command = jq_str(jq_get(payload, "tool_input", "command"))
    except (ValueError, JqError):
        raise DenyError(
            "[shell-write-gate] hook input did not parse — failing closed. Report this to the user."
        ) from None
    agent = jq_str(jq_get(payload, "agent_type"))
    subagent = bool(jq_str(jq_get(payload, "agent_id")))
    coder = bool(script_utils.CODERS.match(agent))
    cwd = jq_str(jq_get(payload, "cwd")) or os.getcwd()
    if not command:
        return

    code = strip_comments(strip_heredocs(command))
    texts = code_texts(code)
    segments = [segment for text in texts
                for _operator, step in shell_command.split_command_steps(text)
                for segment in simple_command_texts(step)]
    targets = [target for text in texts for target in step_targets(text, cwd)]
    text_targets = [target for text in texts if shell_command.names_code_runner(text)
                    for target in regex_written_targets(text, skip_quoted=False)]

    cannot_skip = subagent or coder
    if "#skip-shell-write-gate" in command and not cannot_skip:
        return

    written_paths = {resolve_target(raw_target, cwd) for raw_target, _folders, _unread in targets} - {None}
    for segment in segments:
        target = interpreter_written_target(segment, cwd, written_paths, command)
        if target:
            raise DenyError(deny_text("a script that writes " + target + " bypasses the Write/Edit hook pipeline. "
                                      "Keep any scratch script in the scratchpad, never in the repo tree.",
                                      cannot_skip))

    if not PRECHECK.search(command):
        return

    for segment in segments:
        word = find_editor_word(segment)
        if word is None or not is_inplace(word, segment):
            continue
        target = in_place_target(segment, word)
        raise DenyError(deny_text("in-place editing of " + target + " bypasses the Write/Edit hook pipeline.",
                                  cannot_skip))

    for raw_target, folders, unread_change in targets:
        check_written_target(raw_target, folders, unread_change, cannot_skip, coder)

    for raw_target in text_targets:
        check_written_target(raw_target, [cwd], False, cannot_skip, False)


def in_place_target(segment, editor):
    """The file an in-place editor step names: its last word once redirections are dropped, or the whole segment
    when that word is an option or the editor itself."""
    words = shell_command.segment_words(segment)
    target = words[-1] if words else ""
    if not target or target.startswith("-") or target == editor:
        return segment
    return target


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
    for pattern, family in PROGRAM_FAMILIES:
        if pattern.fullmatch(program):
            return shell_command.INTERPRETER_FAMILIES[family]
    return None


def interpreter_code(segment, cwd, written_paths, command):
    """(code, arguments) an interpreter step runs: the `-c`/`-e` code, or the text of an untracked script file. A
    script the same command writes first (`cat > x.py <<EOF ... && python3 x.py`) does not exist yet, so its code is
    the whole command, heredoc bodies included. None for any other step, a module run, or a git-tracked or
    git-ignored script: tracked code is reviewed, and an ignored file is a build output or dependency rather than an
    ad hoc edit."""
    words = shell_command.command_after_wrappers(shell_command.segment_words(segment), peel_containers=False)
    words = peel_package_runner(words)
    if not words or not INTERPRETER.fullmatch(os.path.basename(words[0])):
        return None

    program = os.path.basename(words[0])
    family = program_family(program)
    arguments = words[1:]
    if program == "deno" and arguments[:1] == ["eval"]:
        code_arguments = arguments[1:]
        while code_arguments and code_arguments[0].startswith("-"):
            code_arguments = code_arguments[1:]
        return (code_arguments[0], code_arguments[1:]) if code_arguments else None
    if program in ("deno", "bun") and arguments[:1] == ["run"]:
        arguments = arguments[1:]

    value_options = set(family["value_options"])
    if program == "deno":
        value_options.update(DENO_VALUE_FLAGS)
    inline_code = re.compile(r"-[a-zA-Z]*[" + family["inline_code_letters"] + "]")
    index = 0
    while index < len(arguments):
        word = arguments[index]
        index += 1
        if inline_code.fullmatch(word) or word in family["inline_code_flags"]:
            return (arguments[index], arguments[index + 1:]) if index < len(arguments) else None
        if word in family["no_stdin_code_flags"]:
            return None
        if word in value_options:
            index += 1
            continue
        if word.startswith("-"):
            continue
        script = resolve_target(word, cwd)
        if script in written_paths:
            return command, arguments[index:]
        if (
            script is None
            or not os.path.isfile(script)
            or is_git_tracked(script)
            or script_utils.is_git_ignored(script)
        ):
            return None
        try:
            if os.path.getsize(script) > MAX_SCRIPT_BYTES:
                return None
            with open(script, encoding="utf-8", errors="replace") as script_file:
                return script_file.read(), arguments[index:]
        except OSError:
            return None
    return None


def write_statements(code):
    """(statement, target) for each file write. The statement is the `;`-separated part of the write's line, so a
    tracked file the code only reads elsewhere does not count. The target is the part of it that names the written
    file."""
    writes = []
    for match in FILE_WRITE.finditer(code):
        line_start = code.rfind("\n", 0, match.start()) + 1
        line_end = code.find("\n", match.end())
        line_end = len(code) if line_end == -1 else line_end
        statement_start = code.rfind(";", line_start, match.start()) + 1 or line_start
        statement_end = code.find(";", match.end(), line_end)
        statement_end = line_end if statement_end == -1 else statement_end
        statement = code[statement_start:statement_end]
        writes.append((statement, write_target_text(statement, match.start() - statement_start)))
    return writes


def write_target_text(statement, write_start):
    """The receiver of `.write_text(` or `.write_bytes(`; the receiver and first argument of a method `.open(`; the
    last argument of a copy, move, rename or perl open; else the first argument of the write call."""
    if statement.startswith(".write_", write_start):
        return receiver_text(statement[:write_start])

    open_paren = statement.find("(", write_start)
    if open_paren == -1:
        write_word = statement[write_start:].split(None, 1)[0]
        arguments_start = write_start + len(write_word)
    else:
        arguments_start = open_paren + 1
    arguments = split_arguments(statement, arguments_start)
    if LAST_ARGUMENT_WRITE.match(statement, write_start):
        return arguments[-1]
    if statement.startswith("open", write_start) and statement[write_start - 1:write_start] == ".":
        # `p.open('w')` writes its receiver; `io.open(path, 'w')` and `codecs.open(...)` write their first argument.
        return receiver_text(statement[:write_start - 1]) + "," + arguments[0]
    return arguments[0]


def binding_texts(code, name):
    """The text that binds `name`: an assignment's right side, a for loop's iterable (the element at the name's
    position in a multi-name target), and for a function parameter, the argument at its position in each call."""
    word = re.escape(name.lstrip("$"))
    parameter = re.compile(rf"(?<![\w$]){word}\b")
    texts = assigned_texts(code, word)
    loop = re.compile(rf"\bfor\s*\(?\s*(?:(?:const|let|var|my)\s+)?(?P<targets>{LOOP_TARGETS}\b{word}\b{LOOP_TARGETS})"
                      r"\s(?:in|of)\s")
    for match in loop.finditer(code):
        iterable = ",".join(split_arguments(code, match.end()))
        targets = [target.strip(" \t\n()[]$") for target in match.group("targets").split(",")]
        position = targets.index(name.lstrip("$")) if name.lstrip("$") in targets else None
        if len(targets) == 1 or position is None:
            texts.append(iterable)
            continue
        if iterable.lstrip().startswith("zip("):
            zip_arguments = split_arguments(iterable, iterable.index("(") + 1)
            texts.append(zip_arguments[position] if position < len(zip_arguments) else iterable)
            continue
        iterable_name = trim(iterable).rstrip(":{").strip(SP).removesuffix(".items()")
        sources = assigned_texts(code, re.escape(iterable_name)) if iterable_name.isidentifier() else []
        fields = [field for source in sources or [iterable] for field in tuple_fields(source, position)]
        texts += [field for field in fields if field.strip()] or [iterable]
    for function in FUNCTION_DEFINITION.finditer(code):
        parameters = [part.strip(SP) for part in function.group(2).split(",")]
        positions = [index for index, part in enumerate(parameters) if parameter.match(part)]
        if not positions:
            continue
        calls = re.finditer(rf"(?<![\w.]){re.escape(function.group(1))}\s*\(", code)
        for call in calls:
            if call.start() == function.start(1):
                continue
            arguments = split_arguments(code, call.end())
            texts.append(arguments[positions[0]] if positions[0] < len(arguments) else ",".join(arguments))
    return texts


def assigned_texts(code, word):
    """The right side of each assignment to the (regex-escaped) name `word`."""
    assignment = re.compile(rf"(?:^|[;{{:])[ \t]*(?:(?:const|let|var|my|our)\s+)?\$?{word}\s*(?::[^=\n]*)?=(?![=>])",
                            re.M)
    return [",".join(split_arguments(code, match.end())) for match in assignment.finditer(code)]


def named_texts(code, text):
    """`text` plus the text that binds each name it uses, followed through MAX_NAME_HOPS bindings."""
    texts = [text]
    frontier = [text]
    seen = set()
    for _hop in range(MAX_NAME_HOPS):
        names = {name for part in frontier for name in CODE_NAME.findall(part)} - seen
        seen |= names
        frontier = [bound for name in sorted(names) for bound in binding_texts(code, name)]
        texts += frontier
    return texts


def path_candidates(text):
    """Each string literal in text, and all of them joined with `/` (`ROOT / "docs" / "a.md"`)."""
    literals = [match.group(2) for match in STRING_LITERAL.finditer(text)]
    joined = ["/".join(literals)] if len(literals) > 1 else []
    return literals + joined


def written_candidates(code):
    """The path texts code's file writes name: each literal in a write statement, and each literal its target is
    bound to."""
    writes = write_statements(code)
    literals = [match.group(2) for statement, _target in writes for match in STRING_LITERAL.finditer(statement)]
    named = [candidate for _statement, target in writes for text in named_texts(code, target)
             for candidate in path_candidates(text)]
    return literals + named


def interpreter_written_target(segment, cwd, written_paths, command):
    """The git-tracked file an interpreter step opens for writing, else None: code with a file write whose statement
    names a tracked file as a string literal, whose target is a name bound (through assignments, for loops and
    function calls) to a tracked file's literal or to literals that join into one, or a tracked file passed as an
    argument. A path the code builds any other way is not seen."""
    found = interpreter_code(segment, cwd, written_paths, command)
    if found is None:
        return None

    raw_code, arguments = found
    if not write_statements(raw_code):
        return None

    # A bracket or quote inside a comment cuts a literal, and a `#` that starts no comment (a JS regex, perl's
    # `s/a #b/`) cuts real code, so trace the code both with and without comments.
    candidates = []
    for code in dict.fromkeys((raw_code, without_comments(raw_code))):
        candidates += written_candidates(code)
    for candidate in candidates + arguments:
        path = resolve_target(candidate, cwd)
        if path and os.path.isfile(path) and is_git_tracked(path):
            return path
    return None


def check_tracked_target(raw_target, folder, cannot_skip, after_directory_change):
    path = resolve_target(raw_target, folder)
    if path is None:
        return
    if os.path.islink(path):
        resolved = os.path.realpath(path)
        if resolved and os.path.exists(shell_dirname(resolved)):
            path = resolved
    if not is_git_tracked(path):
        return

    subject = (path + " is git-tracked. Shell writes bypass the Write/Edit hook pipeline "
               "(comment/prose/budget gates).")
    if after_directory_change:
        subject += " " + DIRECTORY_CHANGE_HINT
    raise DenyError(deny_text(subject, cannot_skip))


def check_written_target(raw_target, folders, unread_change, cannot_skip, coder):
    """Deny a write to a git-tracked file, a relative target after a folder change the gate cannot read, and for a
    coder a relative target after any folder change or a new file outside a temp dir. folders holds the session cwd
    first, then each folder a literal `cd` or `pushd` moved to before the write."""
    cwd = folders[0]
    expanded = expand_env_names(raw_target, ("TMPDIR", "HOME"))
    relative = not path_word_is_absolute(expanded)
    after_directory_change = relative and (unread_change or len(folders) > 1)

    for folder in folders if relative else [cwd]:
        check_tracked_target(raw_target, folder, cannot_skip, after_directory_change)

    if relative:
        if unread_change:
            raise DenyError(deny_text(raw_target + " is a relative write target after a cd to a folder this gate "
                                      "cannot read. " + DIRECTORY_CHANGE_HINT, cannot_skip))
        if coder and after_directory_change:
            raise DenyError(deny_text(raw_target + " is a relative write target after a cd. " + DIRECTORY_CHANGE_HINT,
                                      True))
    if not coder:
        return
    coder_path = resolve_target(expanded, cwd)
    if coder_path is None:
        return
    if "$" in coder_path:
        raise DenyError(deny_text(raw_target + " is a redirect or tee target this gate cannot resolve, so it may "
                                  "create a new file outside a temp dir. Write to an explicit path.", True))
    if not os.path.exists(coder_path) and not is_under_temp_dir(coder_path):
        raise DenyError(deny_text(coder_path + " would be a new file created from the shell, outside a temp dir. "
                                  "A new file bypasses the Write/Edit hook pipeline.", True))


def main():
    if os.environ.get("CLAUDE_SKIP_HOOKS"):
        return 0
    internal = None
    try:
        run(sys.stdin.buffer.read().decode("utf-8", "replace"))
    except DenyError as denied:
        hook_input.emit_decision("deny", str(denied))
    except JqError as error:
        internal = error.rc
    except Exception:
        internal = 1
    if internal is not None:
        hook_input.emit_decision("deny", f"[shell-write-gate] internal error (exit {internal}) — failing closed. "
                                         "Report this to the user.")
    return 0


if __name__ == "__main__":
    hook_input.run_gate(main)
