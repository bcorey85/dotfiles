#!/usr/bin/env python3
"""PreToolUse hook on Bash: deny the inline interpreter runs that bash-safety-gate.sh blocks, with the way around.

The safety gate is generated and must not be edited, and its own block text names no other path, so agents retry
another inline form. This hook runs the gate's own interpreter-inline patterns through the system grep, as the gate
does, so it blocks what the gate blocks on each platform: macOS grep matches the rule across `|`, `;` and `&&` where
GNU grep stops at them. It matches them on the command with its quoted text blanked, as the gate does on a
command it judges read-only; on other commands the gate matches the raw text. So a quoted argument that names a
`-c` flag denies nothing. It also blocks code fed on stdin to a bare interpreter (`python3 -`, a heredoc or
here-string, a pipe in, also into `manage.py shell`), which the gate does not block. It denies with text that says
what to do instead. An error while reading the input or judging the command exits 0 with no output.
"""
import json
import os
import re
import subprocess
import sys

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import shell_command
import shell_statements

INLINE_FLAGS = r"-(c|e|r)|--?(eval|command)"
INLINE = rf"\b(python3?|node|perl|ruby|php)\b[^;|&]*\s({INLINE_FLAGS})\b"
# One word of INLINE's flags, matched as the gate matches them: case-insensitive.
INLINE_FLAG = re.compile(INLINE_FLAGS, re.I)
# ssh: a last word that holds a space is read as a command string it runs.
SSH_COMMAND = "ssh"
# eval: its joined arguments are read as a command string it runs.
EVAL_COMMAND = "eval"
ALLOWED = (r"import\s+(json|sys|os\.path|pathlib|re|math|hashlib|base64|urllib|collections|struct|platform|sysconfig|"
           r"ast|tomllib?|configparser|csv|io|textwrap|shutil|tempfile|glob|fnmatch|copy|pprint|inspect|importlib|"
           r"pkg_resources|packaging|setuptools|distutils)|JSON\.(parse|stringify)|require\(|"
           r"console\.(log|error|warn|dir)|process\.(version|arch|platform|cwd)|Buffer\.(from|alloc)")
HEREDOC_OPERATOR = re.compile(r"<<<?")
PIPE_BOTH = re.compile(r"\|&")
REDIRECT_OPERATOR = re.compile(r"\d*[<>]+&?")
REDIRECT_WORD = re.compile(r"\d*[<>]")
INTERPRETER_FAMILIES = shell_command.INTERPRETER_FAMILIES
INTERPRETER = shell_command.INTERPRETER
TEXT = ("Inline interpreter runs (python3 -c, node -e, perl -e, manage.py shell -c) and code fed on stdin to a bare "
        "interpreter (python3 -, python3 <<'EOF', cat file | python3) are blocked. Do not retry another inline form. "
        "Write the code to a script file in your scratchpad directory with the Write tool, then run the file: "
        "python3 <file>, node <file>, or python manage.py shell < <file>. A script file may still read data on "
        "stdin (python3 <file> <<'EOF'). If the command holds no inline code, run the interpreter step as its own "
        "Bash call, apart from any later -c, -e or -r flag.")


def grep(pattern, command):
    return subprocess.run(["grep", "-qiE", pattern], input=command + "\n", text=True).returncode == 0


def runs_stdin_code(command):
    command = shell_statements.strip_comments(shell_statements.strip_heredocs(command))
    try:
        piped_commands = shell_command.parse_piped_commands(command)
    except ValueError:
        return unparsed_runs_stdin_code(command)

    return any(shell_command.reads_code_from_stdin(words, redirections, piped)
               for words, redirections, piped in piped_commands)


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

    return any(shell_command.reads_code_from_stdin(words, redirections, command_piped or (piped and position == 0))
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
    return shell_command.reads_code_from_stdin(words, redirections, piped)


def split_on_pipe_both(core):
    # The parts of a step's text on each `|&` outside quotes; every part after the first reads from a pipe.
    parts = []
    part_start = 0
    for found in shell_command.unquoted_matches(PIPE_BOTH, core):
        parts.append(core[part_start:found.start()])
        part_start = found.end()
    parts.append(core[part_start:])
    return parts


def without_quoted_text(command):
    """The command with every character inside quotes replaced by `_`, so a `-c` inside a quoted argument (a title
    that names `git -C`) is not read as an interpreter flag. The gate blanks quoted text the same way on a command it
    judges read-only; on other commands the gate matches the raw text."""
    quoted = shell_command.quoted_positions(command)
    return "".join("_" if index in quoted else character for index, character in enumerate(command))


def flags_before_script_run_inline_code(command):
    """True when an interpreter's options before its script file hold an inline-code flag even once its quotes are
    removed, as in `python3 "-c" 'print(1)'`. A word after the script file is the script's own argument."""
    try:
        piped_commands = shell_command.parse_piped_commands(command)
    except ValueError:
        return False

    for words, _redirections, _piped in piped_commands:
        words = shell_command.command_after_wrappers(words)
        if not words or not INTERPRETER.fullmatch(os.path.basename(words[0])):
            continue

        value_options = INTERPRETER_FAMILIES[shell_command.interpreter_family(words[0])]["value_options"]
        options_end = shell_command.skip_options(words, 1, value_options)
        if any(INLINE_FLAG.fullmatch(word) for word in words[1:options_end]):
            return True
    return False


def nested_shell_runs_inline_code(command):
    """True when a shell, eval or ssh step carries a command string that runs inline code, as in
    `bash -c "python3 -c 'print(1)'"`, or a `$(...)` or backtick span does, as in `echo "$(python3 -c 'x')"`;
    blanking quoted text hides that code from the main match."""
    if any(runs_inline_code(span) for span in shell_command.substitution_spans(command)):
        return True

    try:
        piped_commands = shell_command.parse_piped_commands(command)
    except ValueError:
        return False

    for words, _redirections, _piped in piped_commands:
        nested_code = shell_command.shell_code_argument(words)
        if nested_code is None and len(words) >= 2 and os.path.basename(words[0]) == SSH_COMMAND:
            nested_code = words[-1] if re.search(r"\s", words[-1]) else None
        if nested_code is None and len(words) >= 2 and os.path.basename(words[0]) == EVAL_COMMAND:
            nested_code = " ".join(words[1:])
        if nested_code is not None and runs_inline_code(nested_code):
            return True
    return False


def runs_inline_code(command):
    unquoted_command = without_quoted_text(command)
    return (grep(INLINE, unquoted_command) or flags_before_script_run_inline_code(command)
            or nested_shell_runs_inline_code(command))


def blocked(command):
    # Stdin code gets no ALLOWED excuse: the gate does not block it, and `import pathlib` is on that list.
    if runs_stdin_code(command):
        return True
    return bool(INTERPRETER.search(command)) and runs_inline_code(command) and not grep(ALLOWED, command)


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
