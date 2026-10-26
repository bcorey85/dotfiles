"""stale_prose.py: list the prose lines that name a symbol the working tree's diff changed, renamed or removed.

  stale_prose.py [--base REV]       (run from inside a git repo; REV defaults to HEAD)

Symbols come from `git diff -U0 REV` against the working tree, in code files only. Prose is any line of a .md .mdx
.rst or .txt file, a description, summary or title line of a .yaml .yml or .json file, and a comment line of a code
file, found with `git grep` in tracked files; files under docs/plans/ are never searched. Lines the diff added and
declaration lines are left out. A `changed` symbol (declared on a removed and an added line) whose removed and added
declaration lines are equal once number and string literals are masked changed only in a literal value: only the
prose lines that also hold, as a whole word, a literal of the removed line that the added line lacks are listed.
Renamed, removed and body-changed symbols, and every other changed symbol, keep all their lines.

Exit 0: no hit, or every hit was shown on an earlier run. Exit 1: some hit is new (hits are printed up to 60 lines,
the symbols with a new hit first, and inside each the new ones first, marked; the rest are counted and come back on
the next run). Exit 2: git failed, the diff did not parse, or the saved state is unreadable. The hits already shown
are kept, with the commit REV names, in the file that `git rev-parse --git-path stale-prose-shown.json` names; a
different commit starts the list again."""
import argparse
import json
import pathlib
import re
import subprocess
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent.parent / "lib")]
import script_utils
import source_text

PROSE_SUFFIXES = (".md", ".mdx", ".rst", ".txt")
DESCRIPTION_SUFFIXES = (".yaml", ".yml", ".json")
COMMENT_STYLE_OF_SUFFIX = {
    ".ts": "slash", ".tsx": "slash", ".js": "slash", ".jsx": "slash", ".mjs": "slash", ".go": "slash",
    ".rs": "slash", ".java": "slash", ".kt": "slash", ".py": "hash_triple", ".rb": "hash",
}
CODE_SUFFIXES = tuple(COMMENT_STYLE_OF_SUFFIX)
DESCRIPTION_LINE = re.compile(r"""^\s*(?:-\s+)?["']?(?:description|summary|title)["']?\s*:""", re.IGNORECASE)
PLAIN_LOWERCASE = re.compile(r"[a-z]+")
PLAN_EXCLUDES = (":(exclude)docs/plans/",)
SEARCHED_SUFFIXES = (*PROSE_SUFFIXES, *DESCRIPTION_SUFFIXES, *CODE_SUFFIXES)
MIN_NAME_LENGTH = 4
MAX_OUTPUT_LINES = 60
TEXT_LIMIT = 160
NAMES_PER_GREP = 100
GIT_TIMEOUT_SECONDS = 300
SYMBOL_ORDER = ("removed", "changed", "body changed")
HEADER = ("These prose lines name a symbol your diff changed, renamed or removed. Fix each claim that no longer holds "
          "for the code after your change, leave each that still holds, then hand back again.")
NOTHING_NEW = "stale-prose: nothing new: no prose line naming a changed symbol that was not shown before."

KEYWORDS = frozenset({"if", "for", "while", "switch", "catch", "function", "return", "with", "else", "do", "try",
                      "new", "throw", "when", "synchronized", "await", "yield", "typeof", "super"})

JS_MODIFIERS = r"(?:(?:export|default|declare|abstract|async|public|private|protected|static|readonly|override)\s+)*"
JAVA_MODIFIERS = (r"(?:(?:public|private|protected|static|final|abstract|sealed|non-sealed|default|synchronized|"
                  r"native)\s+)")
KOTLIN_MODIFIERS = (r"(?:(?:public|private|protected|internal|open|override|abstract|final|suspend|inline|data|sealed|"
                    r"const|lateinit|companion|enum|annotation|operator|infix|tailrec)\s+)*")
RUST_MODIFIERS = r"(?:pub(?:\([^)]*\))?\s+)?(?:(?:async|unsafe|const|extern(?:\s+\"[^\"]*\")?)\s+)*"
JAVA_TYPE = r"[\w<>\[\].,?]+"

JS_DECLARATIONS = [
    rf"^\s*{JS_MODIFIERS}function\s*\*?\s*(?P<name>[\w$]+)",
    rf"^\s*{JS_MODIFIERS}(?:const|let|var)\s+(?!enum\b)(?P<name>[\w$]+)",
    rf"^\s*{JS_MODIFIERS}(?:const\s+)?(?:class|interface|enum|namespace)\s+(?P<name>[\w$]+)",
    rf"^\s*{JS_MODIFIERS}type\s+(?P<name>[\w$]+)\s*[=<]",
    rf"^\s*{JS_MODIFIERS}(?:(?:get|set)\s+)?\*?(?P<name>[\w$]+)\s*(?:<[^>]*>)?\s*\([^)]*\)\s*(?::\s*[^=;{{]+)?\{{\s*$",
    rf"^\s*{JS_MODIFIERS}(?P<name>[\w$]+)\s*(?::[^=]+)?=\s*(?:async\s*)?(?:\([^)]*\)|[\w$]+)\s*(?::[^=]+)?=>",
]
DECLARATIONS_OF_SUFFIX = {
    ".py": [r"^\s*(?:async\s+)?def\s+(?P<name>\w+)", r"^\s*class\s+(?P<name>\w+)",
            r"^(?P<name>[A-Za-z_]\w*)\s*(?::[^=]+)?=(?!=)"],
    ".go": [r"^func\s+(?:\([^)]*\)\s*)?(?P<name>\w+)", r"^type\s+(?P<name>\w+)", r"^(?:const|var)\s+(?P<name>\w+)"],
    ".rs": [rf"^\s*{RUST_MODIFIERS}(?:fn|struct|enum|trait|type|mod|static|const|union)\s+(?P<name>\w+)"],
    ".java": [rf"^\s*{JAVA_MODIFIERS}*(?:class|interface|enum|record)\s+(?P<name>\w+)",
              rf"^\s*{JAVA_MODIFIERS}+(?:<[^>]+>\s+)?{JAVA_TYPE}\s+(?P<name>\w+)\s*\(",
              rf"^\s*{JAVA_MODIFIERS}+{JAVA_TYPE}\s+(?P<name>\w+)\s*[=;]"],
    ".kt": [rf"^\s*{KOTLIN_MODIFIERS}(?:fun|val|var|class|interface|object|typealias)\s+(?:<[^>]*>\s+)?"
            rf"(?:[\w.]+\.)?(?P<name>\w+)"],
    ".rb": [r"^\s*def\s+(?:self\.)?(?P<name>\w+[?!]?)", r"^\s*(?:class|module)\s+(?P<name>\w+)",
            r"^\s*(?P<name>[A-Z]\w*)\s*=(?!=)"],
}
for _suffix in (".ts", ".tsx", ".js", ".jsx", ".mjs"):
    DECLARATIONS_OF_SUFFIX[_suffix] = JS_DECLARATIONS
DECLARATION_PATTERNS = {suffix: [re.compile(pattern) for pattern in patterns]
                        for suffix, patterns in DECLARATIONS_OF_SUFFIX.items()}


class GitError(Exception):
    pass


def git_output(root, *args, ok_codes=(0,)):
    """The standard output of `git -c core.quotepath=off <args>` run in root, decoded as UTF-8 with no newline
    translation. Raises GitError on any other exit."""
    argv = ["git", "-c", "core.quotepath=off", *args]
    try:
        done = subprocess.run(argv, capture_output=True, timeout=GIT_TIMEOUT_SECONDS, cwd=root)
    except (OSError, subprocess.SubprocessError) as error:
        raise GitError(f"could not run git: {error}") from error
    stdout = done.stdout.decode("utf-8", "replace")
    if done.returncode not in ok_codes:
        stderr = done.stderr.decode("utf-8", "replace")
        raise GitError(f"git {' '.join(args[:2])} failed: {stderr.strip() or stdout.strip()}")
    return stdout


def suffix_of(path):
    return pathlib.PurePath(path).suffix


def declared_names(line, suffix):
    """The names that one line of a file with this suffix declares, as written; [] when it declares none."""
    names = []
    for pattern in DECLARATION_PATTERNS.get(suffix, ()):
        found = pattern.match(line)
        if found and found.group("name") not in KEYWORDS and found.group("name") not in names:
            names.append(found.group("name"))
    return names


def declared_in(file_diff, side, suffix, comment_numbers):
    """{name: [declaration lines]} for the names declared on the `removed` or `added` lines of a file's hunks. A
    comment line of its file, or a string line of a Python file (its number is in comment_numbers), declares
    nothing."""
    lines = [text for hunk in file_diff.hunks for number, text in getattr(hunk, side) if number not in comment_numbers]
    declarations = {}
    for text in lines:
        for name in declared_names(text, suffix):
            declarations.setdefault(name, []).append(text)
    return declarations


def merge_declarations(pooled, declarations):
    for name, texts in declarations.items():
        pooled.setdefault(name, []).extend(texts)


def old_literals_of_value_only_change(removed_lines, added_lines):
    """The literals of the removed declaration lines that the added ones lack, when the two sets of lines are equal
    once number and string literals are masked; [] when the change is more than a literal value (or no literal is
    gone)."""
    masked_removed = {source_text.mask_literals(text) for text in removed_lines}
    masked_added = {source_text.mask_literals(text) for text in added_lines}
    if masked_removed != masked_added:
        return []

    removed_literals = {literal for text in removed_lines for literal in source_text.literals_of(text) if literal}
    added_literals = {literal for text in added_lines for literal in source_text.literals_of(text)}
    return sorted(removed_literals - added_literals)


def comment_numbers_of_text(text, path):
    """The numbers of the comment lines of a file's text (string lines too, for a Python file). Lines are split on
    "\\n" only, as git numbers them."""
    return source_text.comment_line_numbers(text.split("\n"), COMMENT_STYLE_OF_SUFFIX[suffix_of(path)])


def working_tree_text(root, path):
    """The working-tree file as UTF-8 text with no newline translation; "" when it is not a file."""
    file_path = pathlib.Path(root) / path
    if not file_path.is_file():
        return ""

    return file_path.read_bytes().decode("utf-8", "replace")


def comment_lines_of_side(root, base, path, side):
    """The numbers of the comment lines (string lines too, for a Python file) of a file on the `removed` side (the
    file at the base revision) or the `added` side (the working-tree file). An empty set when that side of the file
    does not exist."""
    if side == "removed":
        text = git_output(root, "show", f"{base}:{path}", ok_codes=(0, 128))
    else:
        text = working_tree_text(root, path)
    return comment_numbers_of_text(text, path)


def changed_symbols(diff_files, root, base):
    """{name: how it changed} for the diff's code files. `removed`: declared on a removed line and on no added
    line of any of the diff's files. `changed`: declared on both. `body changed`: named by a hunk header. The removed
    and added names are pooled over all the files, so a symbol moved from one file to another is `changed`. A
    declaration on a comment or string line is no declaration. A name keeps the label that comes first in
    SYMBOL_ORDER. Names shorter than MIN_NAME_LENGTH are left out. Also {name: old literals} for each `changed` name
    whose removed and added declaration lines differ only in their literal values."""
    removed = {}
    added = {}
    body_changed = set()
    for file_diff in diff_files:
        suffix = suffix_of(file_diff.path)
        if suffix not in CODE_SUFFIXES:
            continue

        merge_declarations(removed, declared_in(file_diff, "removed", suffix,
                                                comment_lines_of_side(root, base, file_diff.path, "removed")))
        merge_declarations(added, declared_in(file_diff, "added", suffix,
                                              comment_lines_of_side(root, base, file_diff.path, "added")))
        for hunk in file_diff.hunks:
            body_changed.update(declared_names(hunk.context, suffix))

    both = removed.keys() & added.keys()
    labels = {}
    for label, names in (("body changed", body_changed), ("changed", both), ("removed", removed.keys() - added.keys())):
        labels.update(dict.fromkeys(names, label))

    kept = {name: label for name, label in labels.items() if len(name) >= MIN_NAME_LENGTH}
    symbols = dict(sorted(kept.items(), key=lambda pair: (SYMBOL_ORDER.index(pair[1]), pair[0])))
    old_literals = {}
    for name, label in symbols.items():
        if label == "changed":
            literals = old_literals_of_value_only_change(removed[name], added[name])
            if literals:
                old_literals[name] = literals
    return symbols, old_literals


def name_pattern(name):
    """The regex a prose line must match to name the symbol. A plain lowercase name matches only as `name` or name(;
    any other name matches as a whole word."""
    if PLAIN_LOWERCASE.fullmatch(name):
        return re.compile(rf"`{name}`|(?<![\w$]){name}\(")
    return re.compile(rf"(?<![\w$]){re.escape(name)}(?![\w$])")


def grep_lines(root, names):
    """{(path, line number): text} for every tracked line of a prose, code, yaml or json file outside docs/plans/
    that holds one of the names as a word, found by `git grep`."""
    found = {}
    pathspecs = [f"*{suffix}" for suffix in SEARCHED_SUFFIXES]
    for start in range(0, len(names), NAMES_PER_GREP):
        patterns = [argument for name in names[start:start + NAMES_PER_GREP] for argument in ("-e", name)]
        output = git_output(root, "grep", "-n", "-w", "-I", "-F", "--null", "--no-color", *patterns, "--", *pathspecs,
                            *PLAN_EXCLUDES, ok_codes=(0, 1))
        for row in output.split("\n"):
            path, _, rest = row.partition("\0")
            number, _, text = rest.partition("\0")
            if number.isdigit():
                found[(path, int(number))] = text
    return found


def is_prose_line(root, path, number, text, comment_cache):
    suffix = suffix_of(path)
    if suffix in PROSE_SUFFIXES:
        return True
    if suffix in DESCRIPTION_SUFFIXES:
        return DESCRIPTION_LINE.match(text) is not None
    if suffix not in COMMENT_STYLE_OF_SUFFIX:
        return False

    if path not in comment_cache:
        comment_cache[path] = comment_numbers_of_text(working_tree_text(root, path), path)
    return number in comment_cache[path]


def holds_old_literal(text, literals):
    """True when the text holds one of the literals as a whole word."""
    return any(re.search(rf"(?<![\w$.]){re.escape(literal)}(?![\w$])", text) for literal in literals)


def prose_hits(root, symbols, diff_files, old_literals):
    """{name: [(path, line number, text)]} for the prose lines that name each symbol. A symbol in old_literals
    changed only in a literal value: only its lines that also hold one of those literals count."""
    added_lines = {(file_diff.path, number) for file_diff in diff_files for hunk in file_diff.hunks
                   for number, _ in hunk.added}
    candidates = grep_lines(root, list(symbols))
    patterns = {name: name_pattern(name) for name in symbols}
    comment_cache = {}
    hits = {}
    for (path, number), text in sorted(candidates.items()):
        if (path, number) in added_lines:
            continue
        matched = [name for name, pattern in patterns.items() if pattern.search(text)]
        if not matched or not is_prose_line(root, path, number, text, comment_cache):
            continue

        declared = declared_names(text, suffix_of(path))
        for name in matched:
            if name in declared:
                continue

            if name not in old_literals or holds_old_literal(text, old_literals[name]):
                hits.setdefault(name, []).append((path, number, text.strip()))
    return hits


def hit_key(path, text):
    return f"{path}\t{text}"


def load_shown(state_path, base_sha):
    """The hit keys shown on earlier runs against this base commit; empty when the file is absent or was written for
    another commit."""
    if not state_path.exists():
        return set()
    try:
        state = json.loads(state_path.read_text())
        shown = state["shown"]
        if not isinstance(shown, list):
            raise TypeError(f"\"shown\" is {type(shown).__name__}, expected a list")

        return set(shown) if state.get("base") == base_sha else set()
    except (ValueError, KeyError, TypeError, OSError) as error:
        raise GitError(f"cannot read {state_path} ({error}); delete the file to start again") from error


def ordered_hits(symbols, hits, shown):
    """[(name, path, line number, text, is new)] with the symbols that have a new hit first, and inside a symbol the
    new hits first, so that a cut list always keeps a new hit."""
    rows = []
    for name in symbols:
        symbol_rows = [(name, path, number, text, hit_key(path, text) not in shown)
                       for path, number, text in hits.get(name, [])]
        symbol_rows.sort(key=lambda row: not row[4])
        rows.append(symbol_rows)
    rows.sort(key=lambda symbol_rows: not any(row[4] for row in symbol_rows))
    return [row for symbol_rows in rows for row in symbol_rows]


def report_lines(symbols, rows):
    """(the printed lines, the rows printed, the number of rows left out). A symbol heading counts as a line."""
    printed = []
    shown_rows = []
    heading_of = None
    for row in rows:
        name, path, number, text, is_new = row
        needed = 1 if name == heading_of else 2
        if len(printed) + needed > MAX_OUTPUT_LINES:
            break

        if name != heading_of:
            printed.append(f"{name} ({symbols[name]}):")
            heading_of = name
        marker = "[new] " if is_new else ""
        printed.append(f"{marker}{path}:{number}: {script_utils.one_line(text, TEXT_LIMIT)}")
        shown_rows.append(row)
    return printed, shown_rows, len(rows) - len(shown_rows)


def run(base):
    root = git_output(".", "rev-parse", "--show-toplevel").strip()
    base_sha = git_output(root, "rev-parse", "--verify", "--quiet", "--end-of-options", f"{base}^{{commit}}",
                          ok_codes=(0, 1)).strip()
    if not base_sha:
        raise GitError(f"--base {base!r} is not a commit; expected a revision such as HEAD or a sha")

    state_path = pathlib.Path(git_output(root, "rev-parse", "--path-format=absolute", "--git-path",
                                         "stale-prose-shown.json").strip())
    shown = load_shown(state_path, base_sha)

    # The prose files are in the diff too, so that the lines it added can be left out of the hits.
    pathspecs = [f"*{suffix}" for suffix in SEARCHED_SUFFIXES]
    diff_text = git_output(root, "diff", "-U0", "--no-color", "--no-ext-diff", "--no-textconv", "--no-renames",
                           "--no-prefix", base_sha, "--", *pathspecs)
    diff_files = source_text.parse_unified_diff(diff_text)
    symbols, old_literals = changed_symbols(diff_files, root, base_sha)
    hits = prose_hits(root, symbols, diff_files, old_literals) if symbols else {}
    rows = ordered_hits(symbols, hits, shown)
    if not any(row[4] for row in rows):
        print(NOTHING_NEW)
        return 0

    printed, shown_rows, left_out = report_lines(symbols, rows)
    print(HEADER)
    print("\n".join(printed))
    if left_out:
        print(f"{left_out} more hit(s) not shown.")
    shown_now = shown | {hit_key(path, text) for _, path, _, text, _ in shown_rows}
    script_utils.write_text_atomically(state_path, json.dumps({"base": base_sha, "shown": sorted(shown_now)}, indent=1))
    return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--base", default="HEAD", help="revision the diff is taken from (default HEAD)")
    arguments = parser.parse_args()
    try:
        sys.exit(run(arguments.base))
    except (GitError, ValueError, OSError) as error:
        print(f"stale-prose: {error}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
