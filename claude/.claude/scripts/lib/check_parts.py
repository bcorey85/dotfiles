"""A check made of several parts (a package part, a Python part), run as one shell command, and the reader of what that
command prints. The writer (`join_parts`) and the readers (`failed_part_names`, `part_results`) share the marker words
below, so the two cannot drift.

A joined command runs each part whatever an earlier part exited with. After each part it prints `PART <name> exit
<code>` on its own line, and when any part failed it ends with `FAILED PARTS: <names>` and exits with the last failed
part's code (a 127, tool not found, never replaces an earlier failure's code). The shell code uses only variables that
zsh also allows to be set (`status` is read-only there)."""
import collections
import re

from script_utils import COMMAND_NOT_FOUND_EXIT_CODE

FAILED_PARTS_MARKER = "FAILED PARTS:"
PART_LINE_WORD = "PART"
PART_NAME = re.compile(r"[A-Za-z0-9_-]+")
PART_LINE = re.compile(rf"^{PART_LINE_WORD} (?P<name>{PART_NAME.pattern}) exit (?P<code>\d+)$")

# One part's name, its exit code and the output it printed before its PART line.
PartResult = collections.namedtuple("PartResult", "name code text")


def part_shell_lines(name, commands):
    """The shell lines that run one part and record its result. The part's command sits on its own lines, so a `#`
    comment in it ends at the line and never hides the closing brace."""
    if not PART_NAME.fullmatch(name):
        raise ValueError(f"check part name {name!r} must match {PART_NAME.pattern}")

    step_command = " && ".join(commands)
    record = (f'part_code=$?; printf "\\n{PART_LINE_WORD} {name} exit %s\\n" "$part_code"; '
              f'[ "$part_code" -eq 0 ] || {{ '
              f'[ "$part_code" -eq {COMMAND_NOT_FOUND_EXIT_CODE} ] && [ "$parts_exit" -ne 0 ] '
              f'|| parts_exit=$part_code; '
              f'failed_parts="$failed_parts {name}"; }}')
    return f"{{ {step_command}\n}}; {record}"


def join_parts(parts):
    """One shell command that runs each part (a CheckPart or a (name, commands) pair) whatever an earlier part exited
    with. The steps of a part join with &&. It prints each part's `PART <name> exit <code>` line, and when any part
    failed `FAILED PARTS: <names>`, and exits with the last failed part's exit code, except that a 127 never replaces
    an earlier failure's code. A single part is its plain `&&` command."""
    if len(parts) == 1:
        _, commands = parts[0]
        return " && ".join(commands)

    lines = ["parts_exit=0; failed_parts="]
    lines += [part_shell_lines(name, commands) for name, commands in parts]
    lines.append(f'[ -z "$failed_parts" ] || {{ echo "{FAILED_PARTS_MARKER}$failed_parts"; exit $parts_exit; }}')
    return "\n".join(lines)


def failed_part_names(log_lines):
    """The part names of the log's `FAILED PARTS: <names>` lines, in log order."""
    names = []
    for line in log_lines:
        if line.startswith(FAILED_PARTS_MARKER):
            names.extend(line[len(FAILED_PARTS_MARKER):].split())
    return names


def part_results(output):
    """The PartResult of each part the output's `PART <name> exit <code>` lines close, in output order. A part's text is
    what the output holds between the previous PART line and its own. Output of a command that is not a joined one
    gives []."""
    results = []
    section = []
    for line in output.splitlines():
        found = PART_LINE.match(line.rstrip())
        if not found:
            section.append(line)
            continue

        results.append(PartResult(found.group("name"), int(found.group("code")), "\n".join(section)))
        section = []
    return results
