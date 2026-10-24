"""Read a Makefile as text, without running make: its variables, rules and default goal, and the arguments of a make
command line. Conditionals, includes, `define` blocks, pattern rules and make functions such as `$(shell ...)` are
not evaluated; a reference to a function is left as written. An include or export line, a `define` block and a
conditional line do not end the rule above them."""
import dataclasses
import pathlib
import re

DEFAULT_FILE_NAMES = ("GNUmakefile", "makefile", "Makefile")
MAX_EXPANSION_DEPTH = 10
ASSIGNMENT = re.compile(r"^(?:(?:export|override)\s+)*([A-Za-z_.][\w.\-]*)\s*(::=|:=|\?=|\+=|=)\s*(.*)$")
TARGET_SPECIFIC_ASSIGNMENT = re.compile(r"\s*[\w.\-]+\s*(?:::=|:=|\?=|\+=|=)")
# A conditional line such as `ifeq (...)`, `else ifdef X` or `endif` ends no rule: the recipe lines of every branch
# belong to the target above it.
CONDITIONAL_DIRECTIVE = re.compile(r"^\s*(?:(?:else\s+)?(?:ifeq|ifneq|ifdef|ifndef)|else|endif)(?=\s|$)")
# A directive that is no rule and no assignment: `include` and its spellings, `export` or `unexport` (with or without
# an assignment) and `vpath`. It ends no rule, so the recipe lines after it still belong to the target above it.
NON_RULE_DIRECTIVE = re.compile(r"^\s*(?:-include|sinclude|include|vpath|unexport|export)(?=\s|$)")
DEFINE_START = re.compile(r"^ *(?:(?:export|override)\s+)*define(?=\s|$)")
DEFINE_END = re.compile(r"^ *endef(?=\s|$)")
VARIABLE_REFERENCE = re.compile(r"\$(?:\(([^()$]+)\)|\{([^{}$]+)\}|([@<^$]))")
# A reference such as `$(shell ls)`, `$(X:.c=.o)` or `$(if a,b)` names a function or a substitution, not a variable.
FUNCTION_REFERENCE = re.compile(r"[\s:,]")
RECIPE_PREFIX = re.compile(r"^[\s@\-+]+")
COMMENT = re.compile(r"(?:^|\s)#.*$")
LINE_CONTINUATION = re.compile(r"[ \t]*\\\n[ \t]*")
VARIABLE_ASSIGNMENT_ARGUMENT = re.compile(r"^[A-Za-z_][\w.\-]*[:?+]*=")
# Options of make that take a value as the next word (or attached to a short option).
SHORT_VALUE_OPTIONS = "CfIoWE"
LONG_VALUE_OPTIONS = {"--directory", "--file", "--makefile", "--include-dir", "--old-file", "--assume-old",
                      "--what-if", "--new-file", "--assume-new", "--eval"}
# -j and --jobs take a job count as the next word only when it is a whole number. -l and its long forms take the next
# word as a load value whenever it starts with a digit or `.`, whatever follows (`-l 2x` consumes `2x`).
JOB_COUNT = re.compile(r"^\d+$")
LOAD_VALUE = re.compile(r"^[\d.]")
LONG_LOAD_OPTIONS = {"--load-average", "--max-load"}
# Options after which make runs no recipe line except one marked `+` or one that names `$(MAKE)`, which is not judged:
# it prints the commands (-n), answers a question (-q), touches the targets (-t) or prints its help (-h). Printing the
# data base (-p) still runs the recipes.
NO_RECIPE_SHORT_OPTIONS = set("nqth")
NO_RECIPE_LONG_OPTIONS = {"--dry-run", "--just-print", "--recon", "--question", "--touch", "--help"}
DIRECTORY_OPTIONS = {"-C", "--directory"}
FILE_OPTIONS = {"-f", "--file", "--makefile"}


@dataclasses.dataclass
class MakeArguments:
    """What a make command line asks for: the directory its makefile is read from (relative to where make runs;
    "" when no -C), the -f files, the named targets, whether a NAME=value argument is present and whether an option
    such as -n makes it run no recipe."""
    directory: str = ""
    files: list = dataclasses.field(default_factory=list)
    targets: list = dataclasses.field(default_factory=list)
    has_variable_assignment: bool = False
    runs_no_recipe: bool = False


def parse_make_arguments(words):
    """Read the words after `make`. A -C option relative to an earlier -C adds to it."""
    arguments = MakeArguments()
    index = 0
    while index < len(words):
        word = words[index]
        index += 1
        if word == "--":
            arguments.targets.extend(words[index:])
            break

        option, value, letters = word, None, ""
        if word.startswith("--"):
            option, value, index = read_long_option(words, word, index)
        elif word.startswith("-") and len(word) > 1:
            option, value, index, letters = read_short_options(words, word, index)
        arguments.runs_no_recipe = arguments.runs_no_recipe or runs_no_recipe(option, letters)

        if option in DIRECTORY_OPTIONS and value:
            arguments.directory = str(pathlib.PurePath(arguments.directory) / value)
        elif option in FILE_OPTIONS and value:
            arguments.files.append(value)
        elif word.startswith("-"):
            continue
        elif VARIABLE_ASSIGNMENT_ARGUMENT.match(word):
            arguments.has_variable_assignment = True
        else:
            arguments.targets.append(word)
    return arguments


def read_long_option(words, word, index):
    # Returns (the option, its value, the next index). A value comes after `=` or, for an option that takes one, as
    # the next word.
    option, equals, attached = word.partition("=")
    value = attached if equals else None
    if option in LONG_VALUE_OPTIONS and value is None and index < len(words):
        return option, words[index], index + 1
    if option in LONG_LOAD_OPTIONS and value is None and index < len(words) and LOAD_VALUE.match(words[index]):
        return option, None, index + 1
    if option == "--jobs" and value is None and index < len(words) and JOB_COUNT.match(words[index]):
        return option, None, index + 1
    return option, value, index


def runs_no_recipe(option, letters):
    # True for a long option, or a short option letter in letters, after which make runs no recipe.
    return option in NO_RECIPE_LONG_OPTIONS or bool(NO_RECIPE_SHORT_OPTIONS.intersection(letters))


def read_short_options(words, word, index):
    # Walk a cluster such as `-sj4` or `-Csub`. Returns (the option that took a value, its value, the next index, the
    # letters before the one that took a value).
    for position, letter in enumerate(word[1:], start=1):
        attached = word[position + 1:]
        letters = word[1:position]
        if letter in SHORT_VALUE_OPTIONS:
            if attached:
                return "-" + letter, attached, index, letters
            if index < len(words):
                return "-" + letter, words[index], index + 1, letters
            return "-" + letter, None, index, letters
        if letter == "O":
            # -O takes an output-sync type only attached (`-Onone`); the letters after it are not options.
            return word, None, index, letters
        if letter in "jl":
            # -j takes a job count only when it is a whole number; -l takes a load value when it starts with a digit
            # or `.`.
            number = LOAD_VALUE if letter == "l" else JOB_COUNT
            if not attached and index < len(words) and number.match(words[index]):
                index += 1
            return word, None, index, letters
    return word, None, index, word[1:]


def load_makefile(directory, files=()):
    """The Makefile read from directory, or None when no file is found or one cannot be read. With no files, the
    first of GNUmakefile, makefile and Makefile."""
    directory = pathlib.Path(directory)
    paths = [directory / name for name in files]
    if not paths:
        paths = [directory / name for name in DEFAULT_FILE_NAMES if (directory / name).is_file()][:1]
    if not paths:
        return None

    try:
        text = "\n".join(path.read_text(errors="replace") for path in paths)
    except OSError:
        return None
    return Makefile(text)


def without_define_blocks(lines):
    """The lines with each `define ... endef` block left out, nested blocks included. An unclosed block runs to the
    end."""
    kept = []
    depth = 0
    for line in lines:
        if DEFINE_START.match(line):
            depth += 1
        elif depth and DEFINE_END.match(line):
            depth -= 1
        elif not depth:
            kept.append(line)
    return kept


class Makefile:
    def __init__(self, text):
        self.variables = {"MAKE": "make"}
        self.prerequisites = {}
        self.order_only_prerequisites = {}
        self.recipes = {}
        self.default_goal = None
        self.parse(text.replace("\r\n", "\n"))

    def parse(self, text):
        lines = without_define_blocks(LINE_CONTINUATION.sub(" ", text).split("\n"))
        for line in lines:
            if line.startswith("\t"):
                continue
            assignment = ASSIGNMENT.match(COMMENT.sub("", line))
            if assignment:
                self.assign(*assignment.groups())

        current_targets = []
        for line in lines:
            if line.startswith("\t"):
                for target in current_targets:
                    self.recipes[target].append(line)
                continue
            line = COMMENT.sub("", line)
            if not line.strip():
                continue
            if CONDITIONAL_DIRECTIVE.match(line) or NON_RULE_DIRECTIVE.match(line):
                continue
            if ASSIGNMENT.match(line):
                current_targets = []
                continue
            current_targets = self.add_rule(line)

        goal = self.expand(self.variables.get(".DEFAULT_GOAL", "")).strip()
        if goal:
            self.default_goal = goal

    def assign(self, name, operator, value):
        if operator in (":=", "::="):
            self.variables[name] = self.expand(value)
        elif operator == "?=":
            self.variables.setdefault(name, value)
        elif operator == "+=":
            self.variables[name] = (self.variables.get(name, "") + " " + value).strip()
        else:
            self.variables[name] = value

    def add_rule(self, line):
        # Returns the targets of the rule on this line, so the recipe lines after it can be added to them.
        if ":" not in line:
            return []
        targets_text, _, rest = line.partition(":")
        rest = rest.lstrip(":")
        if TARGET_SPECIFIC_ASSIGNMENT.match(rest):
            return []

        rest, _, inline_recipe = rest.partition(";")
        targets = [target for target in self.expand(targets_text).split() if "%" not in target]
        normal_text, _, order_only_text = self.expand(rest).partition("|")
        prerequisites = normal_text.split()
        order_only_prerequisites = order_only_text.split()
        for target in targets:
            self.prerequisites.setdefault(target, []).extend(prerequisites)
            self.order_only_prerequisites.setdefault(target, []).extend(order_only_prerequisites)
            self.recipes.setdefault(target, [])
            if inline_recipe.strip():
                self.recipes[target].append(inline_recipe)
            if self.default_goal is None and not target.startswith("."):
                self.default_goal = target
        return targets

    def all_prerequisites(self, target):
        """The prerequisites of the target that make builds first: the normal ones, then the order-only ones."""
        return self.prerequisites.get(target, []) + self.order_only_prerequisites.get(target, [])

    def has_rule(self, target):
        return target in self.recipes

    def expand(self, text, target="", prerequisites=(), depth=0):
        if depth > MAX_EXPANSION_DEPTH:
            return ""

        def replacement(match):
            name = match.group(1) or match.group(2)
            if name is None:
                automatic = {"@": target, "<": prerequisites[0] if prerequisites else "",
                             "^": " ".join(prerequisites), "$": "$"}
                return automatic[match.group(3)]
            if FUNCTION_REFERENCE.search(name):
                return match.group(0)
            return self.expand(self.variables.get(name, ""), target, prerequisites, depth + 1)

        return VARIABLE_REFERENCE.sub(replacement, text)

    def recipe_commands(self, target):
        """The shell commands of the target's recipe, with variables expanded and the leading `@`, `-` and `+`
        removed."""
        prerequisites = self.prerequisites.get(target, [])
        commands = []
        for line in self.recipes.get(target, []):
            expanded = self.expand(RECIPE_PREFIX.sub("", line), target, prerequisites)
            command = RECIPE_PREFIX.sub("", expanded)
            if command:
                commands.append(command)
        return commands
