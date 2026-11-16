"""shell_variables.py: the literal values the variables of one shell command text hold when a step uses them.

A value is proven in two ways only: a bare assignment (`S=/tmp/x`, `export S=/tmp/x`) in a step that surely ran before
the use, and a `for` variable over literal words, inside its own loop body. Everything else is unproven and
literal_values returns None for it: a name assigned a second time anywhere (`S=`, `S+=`, `S[1,2]=`), a name that
stands anywhere in the command as a bare word (`read S`, `unset S`, `integer S`, `print -v S`: a builtin may set it;
a backslash before the name or a `$` after it still counts), a name that the quote-removed words of a step show as a
word, as `NAME=` anywhere inside a word (`E=S\\=7` read as arithmetic) or as an assignment (`unset \\S`,
`declare S\\=x`), a name that ends an option cluster of a name-setting builtin (`printf -vS`, `read -raS`), a name the
shell sets or refuses to let a command set (SHELL_SET_NAMES such as `REPLY` and `RANDOM`), a name looped
over twice, a name written as a named descriptor (`{S}>file`), a value or loop word the shell expands (`$`, a
backtick, a glob, a brace, `~`, a space), a target that holds anything beside the references and safe characters (a
glob qualifier, a modifier, `=cmd`), a prefix assignment, an assignment in a group, a loop, an `if`, a pipe, the
background or behind `||`, and any command that can set a variable in a way the reader does not follow (`eval`,
`source`, `trap`, `let`, a function, `select`, `case`, `$((`, any `${...}` but `${NAME}` (it can compute a name), a
subscript that is no integer literal, inside quotes too (`a[S=1]=y`: the subscript is arithmetic; `$a[S-=2]` too), a
name inside a subscript or nameref value (`declare -n R='S[0]'`), a name-setting builtin (`read`, `printf`, `unset`,
`declare`, ...) whose name operand, or whose option word, holds `$`, a
backtick or a backslash anywhere in its step, redirects included (it can compute the name; a format string or another
program's text is no name operand), a `.` behind `nocorrect`, `noglob` or `-`, any
`IFS` (it changes how an unquoted value splits), and `alias`, `setopt`, `unsetopt`, `emulate`, which change what a
later word runs or how a value expands). A reader that cannot tell fails closed.

Toolkit scripts import it after putting scripts/lib on sys.path."""
import itertools
import math
import re
from collections import Counter, namedtuple

import shell_command
import shell_statements
from script_utils import ENV_NAME as NAME

# The characters a value or loop word may hold: nothing the shell expands, splits or quotes. No `=`: zsh expands `=cmd`
# at the start of a value and after each `:`.
SAFE_CHARS = r"[A-Za-z0-9_@%+:,./-]"
SAFE_WORD = re.compile(SAFE_CHARS + "+")
ASSIGNMENT_WORD = (rf"(?P<name>{NAME})=(?:(?P<bare>{SAFE_CHARS}*)(?=\s|$)|\"(?P<double>{SAFE_CHARS}*)\""
                   rf"|'(?P<single>{SAFE_CHARS}*)')")
ASSIGNMENT_WORDS = re.compile(ASSIGNMENT_WORD)
ASSIGNMENT_STEP = re.compile(rf"^\s*(?:export\s+)?(?:{ASSIGNMENT_WORD}(?:\s+|$))+$")
# A name followed by `=`, `+=`, `[subscript]=` or `[subscript]+=` anywhere in the text, in command position or not:
# a name that appears twice is unproven.
# The scan overlaps, so `a[S=1]=` counts `a` and the `S` inside its subscript.
ASSIGNMENT_MENTION = re.compile(rf"(?=(?<![\w$.-])({NAME})(?:\[[^\]]*\])?\+?=)")
# A name that stands alone as a word, after a blank, an operator, a quote, `=` or a backslash and before one of them,
# `?` (zsh `read 'S?prompt'`) or `$`: the argument of a builtin that may set it. `$S` and `${S}` are no bare word.
BARE_NAME = re.compile(rf"(?<![^\s;&|()<>'\"=\\])({NAME})(?![^\s;&|()<>'\"?$\[])")
# Builtins that set the variable an argument word names. The name may be computed (`printf -v "${N/T/S}"`,
# `read $(cat f)`) or attached to an option letter (`printf -vS`), so no regex over the raw text sees it.
NAME_SETTING_BUILTINS = ("declare|typeset|local|readonly|export|read|printf|print|unset|getopts|mapfile|readarray"
                         "|vared|wait|zparseopts|integer|float")
# The builtins whose `-v` option names the variable; every other word of printf and print is text.
PRINT_BUILTINS = ("printf", "print")
# A word that can compute a name: it holds `$`, a backtick or a backslash.
COMPUTED_TEXT = re.compile(r"[$`\\]")
# An option word: a dash and a letter (`-v`, `-vS`, `-raS`), never a format such as `---` or `-%s`.
OPTION_WORD = re.compile(r"-[A-Za-z]")
# `set -A` (zsh) sets an array named by its next word; the option may share a cluster (`-eA`).
SET_ARRAY_OPTION = re.compile(r"-[A-Za-z]*A[A-Za-z]*")
# A parameter expansion that is not exactly `${NAME}`: it may compute a name.
OTHER_EXPANSION = rf"\$\{{(?!{NAME}\}})"
# A quote-removed word that is a name, or starts with `NAME[`.
WORD_MENTION = re.compile(rf"({NAME})(?:$|\[)")
# `NAME=`, `NAME+=` or `NAME[subscript]=` anywhere in a quote-removed word (`E=S\\=7` reads as `E=S=7`, and
# `[[ E -eq 7 ]]` evaluates the value of E as arithmetic).
WORD_ASSIGNMENT = re.compile(rf"(?=(?<![\w$])({NAME})(?:\[[^\]]*\])?\s*\+?=(?!=))")
# The name of a `for` loop: its own bare word.
FOR_HEADER_NAME = re.compile(rf"(\bfor\s+)(?P<name>{NAME})(?=\s+in\b)")
# Names the shell sets with no assignment in the command (`read` sets REPLY, `getopts` sets OPTARG, `cd` sets PWD) and
# names it computes on each read or refuses to take a value for (`RANDOM=/tmp/x` leaves `$RANDOM` a number).
SHELL_SET_NAMES = frozenset({"REPLY", "reply", "OPTARG", "OPTIND", "MAPFILE", "PWD", "OLDPWD", "RANDOM", "SECONDS",
                             "LINENO", "UID", "EUID", "PPID", "BASHPID", "SRANDOM", "EPOCHSECONDS", "EPOCHREALTIME",
                             "HISTCMD", "BASH_COMMAND", "GROUPS", "SHLVL", "_", "MATCH", "MBEGIN", "MEND", "match",
                             "mbegin", "mend", "BASH_REMATCH", "DIRSTACK", "USERNAME", "FUNCNAME", "BASH_SUBSHELL",
                             "BASH_LINENO", "BASH_SOURCE", "BASH_ARGC", "BASH_ARGV", "COPROC", "pipestatus",
                             "histchars", "HISTCHARS", "SHELLOPTS", "BASHOPTS", "BASH_VERSINFO", "BASH_MONOSECONDS",
                             "PATH", "path", "CDPATH", "cdpath", "FPATH", "fpath", "MANPATH", "manpath", "MAILPATH",
                             "mailpath", "MODULE_PATH", "module_path", "FIGNORE", "fignore", "PSVAR", "psvar",
                             "WATCH", "watch"})
# A named file descriptor (`{S}>file`) sets the variable to the descriptor number.
NAMED_FD = re.compile(rf"\{{({NAME})\}}(?=[<>])")
VARIABLE_REFERENCE = re.compile(rf"\$\{{({NAME})\}}|\$({NAME})")
# A `(` or `<` right after a word character, and the run of word characters that ends a text.
ATTACHED_OPENER = re.compile(r"(?<=[^\s;&|()<>])[(<]")
WORD_TAIL = re.compile(r"[^\s;&|()<>]+$")
# What may stay in a target once the references are removed: safe characters inside one pair of quotes, or none.
REFERENCE_FREE_TARGET = re.compile(rf"([\"']?){SAFE_CHARS}*\1")
# A `:` right after a reference starts a zsh modifier (`$S:h`).
MODIFIER_AFTER_NAME = re.compile(rf"\$\{{{NAME}\}}:|\${NAME}:")
# An unbraced reference that quotes or a backslash cut from the name characters after it (`"$S"ps`, `$S\ps`): the
# parser returns the word with the quotes gone, so a reader of that word sees the longer name `$Sps`.
CUT_REFERENCE = re.compile(rf"\${NAME}(?:[\"']|\\)+\w")
# `[[ A -eq B ]]` and `$[E]` evaluate a variable's value as arithmetic, which can assign a name that no word shows. A
# test whose operands are both numeric literals is safe.
_ARITHMETIC_OPERATOR = r"-(?:eq|ne|lt|le|gt|ge)"
ARITHMETIC_TEST = (rf"\[\[(?!\s+\d+\s+{_ARITHMETIC_OPERATOR}\s+\d+\s+\]\])[^\]]*?\s{_ARITHMETIC_OPERATOR}\s")
# Text the reader does not follow: a builtin that sets a name without naming it as a word (`let S++`) or from text,
# a function, `((`, any parameter expansion but `${NAME}`, the `.` command. A name-setting builtin whose name operand
# holds `$`, a backtick or a backslash is read per step (`_Blocks.read_step`).
#
# `alias` can make a later word run `.`, and `trap` runs text the reader never parses; `setopt`, `unsetopt` and
# `emulate` change how a value expands. All fail closed.
# `set` is no such word: `set -o pipefail` is common and `set -a` changes no value.
UNREADABLE = re.compile(r"(?<![\w$./-])(?:eval|source|let|select|case|function|alias|setopt|unsetopt|emulate|trap"
                        r"|export\s+-[a-zA-Z]*n)(?![\w-])"
                        r"|(?<![\w$])IFS(?!\w)"
                        r"|\(\(|(?:^|[;&|(){\n])[ \t]*\.[ \t]|\w[ \t]*\([ \t]*\)"
                        rf"|{OTHER_EXPANSION}|{ARITHMETIC_TEST}|\$\[|(?<![\w./-]){NAME}\[(?!\d*\])")
MAX_VALUES = 64

# A bare assignment step the reader can use: the step index and the value.
Assignment = namedtuple("Assignment", "step value")
# A `for` loop over literal words (words is None for any other list): the steps of its body, first to last.
Loop = namedtuple("Loop", "name words body_start body_end")


class _OpenBlock:
    """A `for`, `while`, `until` or `if` block whose end the scan has not reached."""

    def __init__(self, is_loop, name=None, words=None):
        self.is_loop = is_loop
        self.name = name
        self.words = words
        self.body_start = None


def has_literal_dollar(step):
    """True when a `$` in the step sits in single quotes or after a backslash. The shell passes it as text, but the
    words the parser returns have lost the quotes, so the step cannot be read as a variable use."""
    quote = None
    escaped = False
    for char in step:
        if escaped and char == "$":
            return True
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote != "'":
            escaped = True
            continue
        if quote is None:
            quote = char if char in "'\"" else None
            continue
        if char == "$" and quote == "'":
            return True
        if char == quote:
            quote = None
    return False


def has_attached_glob_syntax(step):
    """True when a `(` or `<` sits against the word text before it (`$S/a(:h:h)`, `$S/a<->`, `S=(a b)`). zsh reads it as
    a glob qualifier, a numeric range or an array, and the command parser cuts the word there, so a target word read
    from the step stops short. A `$(`, a `<(`, a file descriptor before `<` (`2<in`) and a `(` or `<` inside a quoted
    span (a sed script) are no such syntax."""
    for match in shell_command.unquoted_matches(ATTACHED_OPENER, step):
        opener = match.group(0)
        run = WORD_TAIL.search(step[:match.start()]).group(0)
        if run.endswith("$") or (opener == "<" and run.isdigit()):
            continue
        return True
    return False


def variable_names(text):
    """The names of the variables the text refers to as `$NAME` or `${NAME}`, in order; None when the text holds
    anything else than those references and safe characters (inside one pair of quotes at most): any other `$`, a
    backtick, a subscript, a glob or qualifier, a brace list, `~`, a backslash; a modifier after a name; or a leading
    `=` (zsh's `=cmd`)."""
    names = [match.group(1) or match.group(2) for match in VARIABLE_REFERENCE.finditer(text)]
    rest = VARIABLE_REFERENCE.sub("", text)
    if not REFERENCE_FREE_TARGET.fullmatch(rest) or MODIFIER_AFTER_NAME.search(text):
        return None
    if text.lstrip("\"'").startswith("="):
        return None
    return names


def is_plain_redirect_word(word):
    """True for a redirect word that computes nothing (`>/dev/null`, `2>f`, `&>f`): it is no command word and no
    operand of a name-setting builtin. A redirect that holds `$`, a backtick or a backslash stays a word."""
    return shell_command.is_redirect_word(word) and not COMPUTED_TEXT.search(word)


def name_setting_words(words):
    """The command word and arguments of a name-setting builtin, once leading keywords and wrappers are dropped; an
    empty list for any other command."""
    words = [word for word in words if not is_plain_redirect_word(word)]
    command_words = shell_command.command_after_wrappers(words)
    if not command_words:
        return []
    if command_words[0] == "set" and any(SET_ARRAY_OPTION.fullmatch(word) for word in command_words[1:]):
        return command_words
    if not re.fullmatch(NAME_SETTING_BUILTINS, command_words[0]):
        return []
    return command_words


def option_cluster_names(words):
    """The names that end an option word of a name-setting builtin: `-raS` gives `raS`, `aS` and `S`. A builtin takes
    the name after `-v` or `-a` as one word (`printf -vS`), and counting too many only fails closed."""
    command_words = name_setting_words(words)
    names = []
    for word in command_words[1:]:
        if not word.startswith("-"):
            continue
        for start in range(2, len(word)):
            if re.fullmatch(NAME, word[start:]):
                names.append(word[start:])
    return names


def has_computed_name_word(words):
    """True when a word of a name-setting builtin that can name a variable holds `$`, a backtick or a backslash: an
    option word, the word after `-v` of printf and print, and every operand of any other builtin up to its `=`."""
    command_words = name_setting_words(words)
    if not command_words:
        return False
    head, arguments = command_words[0], command_words[1:]
    candidates = [word for word in arguments if OPTION_WORD.match(word)]
    if head in PRINT_BUILTINS:
        candidates += [after for before, after in itertools.pairwise(arguments) if before == "-v"]
    else:
        candidates += [word.split("=", 1)[0] for word in arguments if not word.startswith("-")]
    return any(COMPUTED_TEXT.search(word) for word in candidates)


def word_mentions(steps):
    """How often each name is set or may be set in the quote-removed words of the steps: a word equal to NAME or
    starting with `NAME[`, a `NAME=` anywhere inside a word, and a name that ends an option cluster of a name-setting
    builtin; the name of a `for` header is no mention. It sees `\\S`, `S\\=x` and `printf -vS`, which the raw text
    hides."""
    mentions = Counter()
    for _, step in steps:
        words = shell_command.segment_words(step)
        for index, word in enumerate(words):
            if index and words[index - 1] == "for":
                continue
            found = WORD_MENTION.match(word)
            if found:
                mentions[found.group(1)] += 1
            mentions.update(match.group(1) for match in WORD_ASSIGNMENT.finditer(word))
        mentions.update(option_cluster_names(words))
    return mentions


def name_mentions(code, steps):
    """How often each name is set or may be set in the code: once for each `NAME=`, `NAME+=` or `NAME[...]=`, and once
    for each bare word NAME other than the name of a `for` header, and once for each named descriptor `{NAME}>` or
    `{NAME}<`. A name counts as often as the raw text or the quote-removed words of the steps show it, whichever is
    more."""
    mentions = Counter(match.group(1) for match in ASSIGNMENT_MENTION.finditer(code))
    without_for_names = FOR_HEADER_NAME.sub(r"\1", code)
    mentions.update(match.group(1) for match in BARE_NAME.finditer(without_for_names))
    mentions.update(match.group(1) for match in NAMED_FD.finditer(code))
    for name, count in word_mentions(steps).items():
        mentions[name] = max(mentions[name], count)
    return mentions


def fill_names(text, values):
    """The text with each `$NAME` and `${NAME}` replaced by values[NAME]."""
    return VARIABLE_REFERENCE.sub(lambda found: values[found.group(1) or found.group(2)], text)


def literal_words(words):
    """The words when each is one literal path piece the shell leaves alone, else None."""
    if not words or not all(SAFE_WORD.fullmatch(word) for word in words):
        return None
    if any(".." in word.split("/") for word in words):
        return None
    return list(words)


class _Blocks:
    """The compound commands open at each step, read from each step's keywords."""

    def __init__(self):
        self.open = []
        self.loops = []
        self.readable = True

    def read_step(self, index, step):
        words = shell_command.segment_words(step)
        position = 0
        while position < len(words) and words[position] in shell_command.GROUP_WORDS:
            self.keyword(words[position], index)
            position += 1
        if self.runs_dot_command(words[position:]) or has_computed_name_word(words[position:]):
            self.readable = False
        head = words[position] if position < len(words) else ""
        if head == "for":
            self.open_for(words[position:])
        elif head == "done":
            self.close(index, is_loop=True)
        elif head == "fi":
            self.close(index, is_loop=False)

    @staticmethod
    def runs_dot_command(words):
        """True when the step's command word, after wrappers (`command .`, `builtin .`), is `.`: it runs a file that
        can set any name. `source` and `eval` are caught by UNREADABLE as words anywhere in the text."""
        command_words = shell_command.command_after_wrappers(words)
        return bool(command_words) and command_words[0] == "."

    def keyword(self, word, index):
        if word == "if":
            self.open.append(_OpenBlock(is_loop=False))
        elif word in ("while", "until"):
            self.open.append(_OpenBlock(is_loop=True))
        elif word == "do":
            self.start_body(index)

    def start_body(self, index):
        if not self.open or not self.open[-1].is_loop or self.open[-1].body_start is not None:
            self.readable = False
            return
        self.open[-1].body_start = index

    def open_for(self, words):
        """Open a `for` block from the words of its header; a word the shell expands makes the loop words None."""
        if len(words) < 3 or words[2] != "in" or not re.fullmatch(NAME, words[1]):
            self.readable = False
            return
        self.open.append(_OpenBlock(True, words[1], literal_words(words[3:])))

    def close(self, index, is_loop):
        if not self.open or self.open[-1].is_loop != is_loop:
            self.readable = False
            return
        block = self.open.pop()
        if is_loop and block.body_start is None:
            self.readable = False
        elif block.name:
            self.loops.append(Loop(block.name, block.words, block.body_start, index - 1))


def opens_backtick_span(step):
    """True when the step holds any backtick: the group depth counter reads no backtick substitution, so an assignment
    on the lines inside one may run in a subshell. A quoted or escaped backtick counts too, which fails closed."""
    return "`" in step


def hides_subshell_or_glob(code, steps):
    """True when the code holds syntax that can run an assignment away from the main shell or inside a word: a step
    with a backtick, a step with attached glob syntax (a qualifier runs code), a heredoc fed to a shell
    (its body reads no variable of this shell), or an unbraced `$NAME:` modifier."""
    if MODIFIER_AFTER_NAME.search(code):
        return True
    if any(shell_statements.opens_shell_heredoc(line) for line in code.splitlines() if "<<" in line):
        return True
    return any(opens_backtick_span(step) or has_attached_glob_syntax(step) for _, step in steps)


class ShellVariables:
    """The variables of one command text (comments and heredoc bodies already removed), read once."""

    def __init__(self, code):
        self.steps = shell_command.split_command_steps(code)
        self.readable = not UNREADABLE.search(code) and not hides_subshell_or_glob(code, self.steps)
        self.mentions = name_mentions(code, self.steps)
        self.assignments = {}
        self.loops = []
        # Whether or not the command is readable: a name a `for` header loops over is never read from the environment.
        self.loop_names = {match.group("name") for match in FOR_HEADER_NAME.finditer(code)}
        if self.readable:
            self.scan()

    @property
    def assigned_names(self):
        """Every name the command sets, may set or loops over, so a caller never reads one from the environment."""
        return frozenset(self.mentions) | self.loop_names

    def scan(self):
        blocks = _Blocks()
        group_depth = 0
        paren_depth = 0
        for index, (operator, step) in enumerate(self.steps):
            blocks.read_step(index, step)
            if not blocks.open and not group_depth and self.usable_assignment(index, operator):
                self.record_assignment(index, step)
            group_depth = max(0, group_depth + shell_command.group_depth_change(step))
            paren_depth = max(0, paren_depth + shell_command.paren_depth_change(step))
            # A `}` closes only a `{` group. Inside a `( ... )` subshell it is a plain word (bash), so the depth
            # counter would drop the subshell too early.
            if paren_depth and shell_command.closes_brace_group(step):
                self.readable = False
        if blocks.open or not blocks.readable:
            self.readable = False
        self.loops = blocks.loops

    def usable_assignment(self, index, operator):
        """True when the step at index runs in the main shell: not piped, not backgrounded, not behind `||`."""
        if operator not in ("", ";", "&&"):
            return False
        following = self.steps[index + 1][0] if index + 1 < len(self.steps) else ""
        return following != "|" and not shell_command.step_runs_in_background(self.steps, index)

    def record_assignment(self, index, step):
        if not ASSIGNMENT_STEP.match(step):
            return
        for found in ASSIGNMENT_WORDS.finditer(step):
            value = next(group for group in found.group("bare", "double", "single") if group is not None)
            self.assignments[found.group("name")] = Assignment(index, value)

    def assignment_value(self, name, step_index):
        """The value of the one assignment of name that surely ran before the step, else None."""
        found = self.assignments.get(name)
        if found is None or self.mentions[name] != 1 or name in self.loop_names or found.step >= step_index:
            return None
        starts_chain = self.steps[found.step][0] != "&&"
        if not starts_chain and not shell_command.runs_only_after_success(self.steps, found.step, step_index):
            return None
        if ".." in found.value.split("/"):
            return None
        return [found.value]

    def loop_values(self, name, step_index):
        """The words of the one loop over name, when its body holds the step, else None. A second loop over the name,
        enclosing the step or not, leaves the name unproven."""
        over_name = [loop for loop in self.loops if loop.name == name]
        if len(over_name) != 1 or self.mentions[name]:
            return None
        loop = over_name[0]
        if not loop.body_start <= step_index <= loop.body_end:
            return None
        return loop.words

    def values_of(self, name, step_index):
        if name in SHELL_SET_NAMES:
            return None
        if name in self.loop_names:
            return self.loop_values(name, step_index)
        return self.assignment_value(name, step_index)

    def literal_values(self, text, step_index):
        """Every literal text that `text` (a redirect or tee target) can expand to when the shell runs the step at
        step_index, or None when a variable in it has no proven value, the step quotes a `$` or cuts a reference from
        the name characters after it (CUT_REFERENCE), the command is unreadable, or the expansions pass MAX_VALUES."""
        names = variable_names(text)
        step = self.steps[step_index][1]
        if names is None or not self.readable or has_literal_dollar(step) or CUT_REFERENCE.search(step):
            return None
        unique = list(dict.fromkeys(names))
        value_lists = [self.values_of(name, step_index) for name in unique]
        if any(not values for values in value_lists) or math.prod(len(v) for v in value_lists) > MAX_VALUES:
            return None
        expansions = []
        for combination in itertools.product(*value_lists):
            values_by_name = dict(zip(unique, combination, strict=True))
            expansions.append(fill_names(text, values_by_name))
        return list(dict.fromkeys(expansions))
