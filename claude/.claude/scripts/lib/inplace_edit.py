"""inplace_edit.py: find an in-place editor (sed -i, perl -pi, awk -i inplace) in a command text and the files it edits.

The shell write gate imports it after putting scripts/lib on sys.path."""
import re

import shell_command
from code_text import SPC
from script_utils import ENV_NAME

SED_INPLACE = re.compile(r"(^|" + SPC + r")(-[a-zA-Z]*i|--in-place(" + SPC + r"|=|$))")
PERL_I = re.compile(r"(^|" + SPC + r")-[a-zA-Z]*i")
PERL_PN = re.compile(r"(^|" + SPC + r")-[a-zA-Z]*[pn]")
AWK_INPLACE = re.compile(r"(^|" + SPC + r")-i" + SPC + "*inplace")
SED_PROGRAMS = ("sed", "gsed")
AWK_PROGRAMS = ("awk", "gawk")
EDITORS = (*SED_PROGRAMS, "perl", *AWK_PROGRAMS)
INVOKERS = ("xargs", "-exec", "-execdir", "sh", "bash", "zsh", "-c", "parallel")
# The options of each editor whose value is the next word, and the ones whose value is its script.
VALUE_OPTIONS = {"sed": ("-l", "--line-length"), "perl": ("-I",), "awk": ("-v", "-F", "-W", "-i")}
SCRIPT_OPTIONS = {"sed": ("-e", "--expression", "-f", "--file"), "perl": ("-e", "-E"),
                  "awk": ("-f", "--file", "-e", "--source")}
# Words an invoker such as `find -exec` leaves in the editor's arguments.
INVOKER_WORDS = (";", "\\;", "+")
# A short flag group that ends in the flag that hands the editor its script: sed's `-e`, perl's `-e` and `-E`. A sed
# `-E` is its extended-regex flag, and awk has no combined script flag.
COMBINED_SCRIPT_FLAGS = {"sed": re.compile(r"^-[a-zA-Z0-9]*e$"), "perl": re.compile(r"^-[a-zA-Z0-9]*[eE]$")}
ASSIGNMENT_OPERAND = re.compile(rf"^{ENV_NAME}=")
# The operand an editor behind `xargs`, `parallel` or `fd -x` gets from the invoker: it names no file the gate can see.
UNKNOWN_OPERAND = "(the files its invoker passes in)"
STDIN_FILE_INVOKERS = ("xargs", "parallel")
# fd appends each matched path to the editor's arguments when the command holds no `{}`.
FD_PROGRAMS = ("fd", "fdfind")
FD_EXEC_OPTION = re.compile(r"^(-[A-Za-z0-9]*[xX]|--exec(-batch)?(=.*)?)$")


def is_inplace(program, segment):
    if program in SED_PROGRAMS:
        return bool(SED_INPLACE.search(segment))
    if program == "perl":
        return bool(PERL_I.search(segment)) and bool(PERL_PN.search(segment))
    if program in AWK_PROGRAMS:
        return bool(AWK_INPLACE.search(segment))
    return False


def is_invoker_option(word, command_words):
    """True when the word is fd's `-x`, `-X` or `--exec` option and the step's command word is fd: the same letters
    mean something else to every other command (`ssh -X`, `grep -x`)."""
    return runs_fd(command_words) and bool(FD_EXEC_OPTION.match(word))


def runs_fd(command_words):
    return bool(command_words) and command_words[0].rsplit("/", 1)[-1] in FD_PROGRAMS


def has_unseen_files(operands):
    """True when the operands include a file list the gate cannot see: the invoker's own list (`xargs`, `parallel`,
    `fd -x`), `find -exec`'s `{}`, or a segment it could not read. No such list is ever a scratch file."""
    return any(operand == UNKNOWN_OPERAND or "{}" in operand for operand in operands)


def find_editor_word(segment):
    # The in-place editor a step runs: its command word once the wrappers are dropped, or an editor named after an
    # invoker (`xargs sed -i`, `find -exec sed -i`, `sh -c`).
    # A docker, podman, kubectl or ssh call runs its editor elsewhere: its wrapper words are not peeled.
    command_words = shell_command.command_after_wrappers(shell_command.words_by_blank(segment), peel_containers=False)
    invoked = False
    for index, word in enumerate(command_words):
        base = word.rsplit("/", 1)[-1]
        if base in EDITORS and (index == 0 or invoked):
            return base
        if base in INVOKERS or is_invoker_option(word, command_words):
            invoked = True
    return None


def editor_family(editor):
    if editor in SED_PROGRAMS:
        return "sed"
    if editor in AWK_PROGRAMS:
        return "awk"
    return editor


def gives_script(family, option):
    """True when the option hands the editor its script: `-e CODE`, `--expression=CODE`, or a short flag group that
    ends in the family's script flag (`-ne`) and holds no `i`, which would read the `e` as a backup suffix."""
    if option in SCRIPT_OPTIONS[family] or option.split("=", 1)[0] in SCRIPT_OPTIONS[family]:
        return True
    combined = COMBINED_SCRIPT_FLAGS.get(family)
    return combined is not None and bool(combined.match(option)) and "i" not in option


def takes_next_word(family, option):
    """True when the option is the whole flag and the editor reads the next word as its value."""
    if option in VALUE_OPTIONS[family] or option in SCRIPT_OPTIONS[family]:
        return True
    return gives_script(family, option) and "=" not in option and not option.startswith("--")


def without_bsd_backup_suffix(family, args):
    """The sed arguments with the empty word dropped that follows a bare `-i` (BSD sed's empty backup suffix, which is
    no script and no file)."""
    if family != "sed":
        return args
    return [word for index, word in enumerate(args) if not (word == "" and index and args[index - 1] == "-i")]


def read_option(family, option, rest):
    """Drop from rest the value the option takes; True when the option handed the editor its script."""
    if takes_next_word(family, option):
        next(rest, None)
    return gives_script(family, option)


def file_operands(segment, editor):
    """The words an in-place editor step reads as files: what follows the editor once its options and its script (the
    first word that is no option, unless an option gave the script) are dropped. Empty when none can be found."""
    # A backslash at a line end joins two lines; shlex would hand it back as a one-newline word.
    joined_lines = shell_command.LINE_CONTINUATION.sub(" ", segment)
    words = shell_command.words_without_redirections(joined_lines)
    if words is None:
        return []
    start = next((index for index, word in enumerate(words) if word.rsplit("/", 1)[-1] == editor), None)
    if start is None:
        return []
    family = editor_family(editor)
    script_given = False
    operands = []
    rest = iter(without_bsd_backup_suffix(family, words[start + 1:]))
    for word in rest:
        if word == "--":
            operands += list(rest)
            break
        if word.startswith("-") and len(word) > 1:
            script_given = read_option(family, word, rest) or script_given
            continue
        operands.append(word)
    if not script_given and operands:
        operands = operands[1:]
    # Only awk reads `NAME=value` as an assignment; sed and perl open it as a file.
    drops_assignments = family == "awk"
    files = [word for word in operands
             if word not in INVOKER_WORDS and not (drops_assignments and ASSIGNMENT_OPERAND.match(word))]
    command_words = shell_command.command_after_wrappers(words, peel_containers=False)
    before_editor = words[:start]
    if any(word.rsplit("/", 1)[-1] in STDIN_FILE_INVOKERS or is_invoker_option(word, command_words)
           for word in before_editor):
        files.append(UNKNOWN_OPERAND)
    return files
