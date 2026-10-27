#!/usr/bin/env python3
"""PreToolUse hook on Bash: deny the inline interpreter runs that bash-safety-gate.sh blocks, with the way around.

The safety gate is generated and must not be edited, and its own block text names no other path, so agents retry
another inline form. This hook runs the gate's own interpreter-inline patterns through the system grep, as the gate
does, so it blocks what the gate blocks on each platform: macOS grep matches the rule across `|`, `;` and `&&` where
GNU grep stops at them. It also blocks code fed on stdin to a bare interpreter (`python3 -`, a heredoc or here-string,
a pipe in, also into `manage.py shell`), which the gate does not block. It denies with text that says what to do
instead. An error while reading the input or judging the command exits 0 with no output.
"""
import json
import os
import re
import subprocess
import sys

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import shell_command
import shell_statements

INLINE = r"\b(python3?|node|perl|ruby|php)\b[^;|&]*(\s-(c|e|r)\b|\s--?(eval|command)\b)"
ALLOWED = (r"import\s+(json|sys|os\.path|pathlib|re|math|hashlib|base64|urllib|collections|struct|platform|sysconfig|"
           r"ast|tomllib?|configparser|csv|io|textwrap|shutil|tempfile|glob|fnmatch|copy|pprint|inspect|importlib|"
           r"pkg_resources|packaging|setuptools|distutils)|JSON\.(parse|stringify)|require\(|"
           r"console\.(log|error|warn|dir)|process\.(version|arch|platform|cwd)|Buffer\.(from|alloc)")
HEREDOC_OPERATOR = re.compile(r"<<<?")
PIPE_BOTH = re.compile(r"\|&")
REDIRECT_OPERATOR = re.compile(r"\d*[<>]+&?")
REDIRECT_WORD = re.compile(r"\d*[<>]")
# Words that name stdin as the program file of an interpreter, like `-`.
STDIN_PROGRAM_FILES = {"-", "/dev/stdin", "/dev/fd/0", "/proc/self/fd/0"}
# Redirections that carry code inside the command: a heredoc or a here-string. A file read with `<` is a script file,
# as in `python3 <file>`.
STDIN_CODE_REDIRECTIONS = {"<<", "<<<"}
# By interpreter family: the name pattern, the flags after which it runs no program from stdin (a module, a version,
# help), and the options that take the next word as their value. nodejs is the node family.
INTERPRETER_FAMILIES = {
    "python": {"name": r"python[\d.]*", "no_stdin_code_flags": {"-m", "-V", "-VV", "--version", "-h", "--help"},
               "value_options": {"-W", "-X", "-Q"}},
    "perl": {"name": r"perl", "no_stdin_code_flags": {"-v", "-V", "--version", "-h", "--help"},
             "value_options": {"-I", "-M", "-C"}},
    "ruby": {"name": r"ruby", "no_stdin_code_flags": {"-v", "--version", "-h", "--help"},
             "value_options": {"-I", "-r", "-C", "-E"}},
    "node": {"name": r"node(?:js)?", "no_stdin_code_flags": {"-v", "--version", "-h", "--help"},
             "value_options": {"-r", "--require", "--import", "-C", "--conditions"}},
    "php": {"name": r"php", "no_stdin_code_flags": {"-v", "--version", "-h", "--help"},
            "value_options": {"-d", "-c", "-r"}},
}
INTERPRETER = re.compile("|".join(family["name"] for family in INTERPRETER_FAMILIES.values()), re.I)
MANAGE_SCRIPT = "manage.py"
TEXT = ("Inline interpreter runs (python3 -c, node -e, perl -e, manage.py shell -c) and code fed on stdin to a bare "
        "interpreter (python3 -, python3 <<'EOF', cat file | python3) are blocked. Do not retry another inline form. "
        "Write the code to a script file in your scratchpad directory with the Write tool, then run the file: "
        "python3 <file>, node <file>, or python manage.py shell < <file>. A script file may still read data on "
        "stdin (python3 <file> <<'EOF'). If the command holds no inline code, run the interpreter step as its own "
        "Bash call, apart from any later -c, -e or -r flag.")


def grep(pattern, command):
    return subprocess.run(["grep", "-qiE", pattern], input=command + "\n", text=True).returncode == 0


def reads_code_from_stdin(words, redirections, piped):
    """True when the simple command runs a bare interpreter whose program text arrives on stdin: `python3 -`, a
    heredoc or here-string into it, or a pipe into it. An interpreter given a script file (also by `<`), `-m` or a
    version flag reads stdin as data, not as code. `manage.py shell` is a bare interpreter: it runs stdin as code."""
    words = shell_command.command_after_wrappers(words)
    if not words:
        return False

    if os.path.basename(words[0]) == MANAGE_SCRIPT:
        words = ["python", *words]
    if not INTERPRETER.fullmatch(os.path.basename(words[0])):
        return False

    interpreter_family = re.match(r"[a-z]+", os.path.basename(words[0]).lower()).group()
    interpreter_family = "node" if interpreter_family == "nodejs" else interpreter_family
    value_options = INTERPRETER_FAMILIES[interpreter_family]["value_options"]
    no_stdin_code_flags = INTERPRETER_FAMILIES[interpreter_family]["no_stdin_code_flags"]
    index = 1
    while index < len(words):
        word = words[index]
        if word in STDIN_PROGRAM_FILES:
            return True
        if os.path.basename(word) == MANAGE_SCRIPT and words[index + 1:index + 2] == ["shell"]:
            break
        if interpreter_family == "python" and word.startswith("-m") and len(word) > 2:
            return False
        if word in no_stdin_code_flags or not word.startswith("-"):
            return False
        index += 2 if word in value_options else 1

    has_stdin_code = any(operator in STDIN_CODE_REDIRECTIONS for operator, _target in redirections)
    return piped or has_stdin_code


def runs_stdin_code(command):
    command = shell_statements.strip_comments(shell_statements.strip_heredocs(command))
    try:
        piped_commands = shell_command.parse_piped_commands(command)
    except ValueError:
        return unparsed_runs_stdin_code(command)

    return any(reads_code_from_stdin(words, redirections, piped) for words, redirections, piped in piped_commands)


def unparsed_runs_stdin_code(command):
    """runs_stdin_code for a command that parse_piped_commands cannot read: each quote-aware step is read with
    parse_piped_commands piece by piece, and split on whitespace only where that fails; a heredoc or here-string
    outside quotes ends the words of a piece split that way."""
    for operator, step in shell_command.split_command_steps(command):
        core, tail = shell_command.step_parts(step)
        for part_index, part in enumerate(split_on_pipe_both(core + " " + tail)):
            if part_reads_stdin_code(part, part_index > 0 or operator == "|"):
                return True
    return False


def part_reads_stdin_code(part, piped):
    # One piece of a step between `|&` operators; piped is True when a pipe feeds its first command.
    try:
        piped_commands = shell_command.parse_piped_commands(part)
    except ValueError:
        return split_part_reads_stdin_code(part, piped)

    return any(reads_code_from_stdin(words, redirections, command_piped or (piped and position == 0))
               for position, (words, redirections, command_piped) in enumerate(piped_commands))


def split_part_reads_stdin_code(part, piped):
    # The fallback for a part the parser cannot read: split on whitespace, a heredoc or here-string outside quotes
    # ends the words, and a redirection word is dropped with its target.
    redirections = []
    heredocs = shell_command.unquoted_matches(HEREDOC_OPERATOR, part)
    if heredocs:
        redirections.append((heredocs[0].group(), ""))
        part = part[:heredocs[0].start()]

    words = []
    skip_target = False
    for word in part.split():
        if skip_target:
            skip_target = False
        elif REDIRECT_OPERATOR.fullmatch(word):
            skip_target = True
        elif REDIRECT_WORD.match(word):
            continue
        else:
            words.append(word)
    return reads_code_from_stdin(words, redirections, piped)


def split_on_pipe_both(core):
    # The parts of a step's text on each `|&` outside quotes; every part after the first reads from a pipe.
    parts = []
    part_start = 0
    for found in shell_command.unquoted_matches(PIPE_BOTH, core):
        parts.append(core[part_start:found.start()])
        part_start = found.end()
    parts.append(core[part_start:])
    return parts


def blocked(command):
    # Stdin code gets no ALLOWED excuse: the gate does not block it, and `import pathlib` is on that list.
    if runs_stdin_code(command):
        return True
    return bool(INTERPRETER.search(command)) and grep(INLINE, command) and not grep(ALLOWED, command)


def main():
    try:
        payload = json.loads(sys.stdin.read())
        command = (payload.get("tool_input") or {}).get("command")
        if not os.environ.get("CLAUDE_SKIP_HOOKS") and isinstance(command, str) and blocked(command):
            sys.stdout.write(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": TEXT}}))
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
