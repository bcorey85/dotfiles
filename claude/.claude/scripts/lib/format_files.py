"""The repo's autofix formatters, run on a list of files: oxlint or eslint --fix and oxfmt or prettier for web and
document files, and (when asked) ruff for Python files. Also `lint_problems`, a check-mode lint that fixes nothing:
ruff, oxlint or eslint, returning (command, output) per failing linter. Any repo, any file list."""
import contextlib
import json
import os
import pathlib
import re
import shutil
import subprocess
from collections import namedtuple

import hook_input
import oxlint_ignore
import script_utils
from plan_format import PLANS_DIR
from toml_file import read_toml
from worktree_snapshot import UNREADABLE, file_hash

LINT_TIMEOUT_SECONDS = 300
LINT_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".vue")
FORMAT_ONLY_SUFFIXES = (".json", ".css", ".scss", ".md")
PYTHON_SUFFIX = ".py"
PROMPT_MARKDOWN_DIR = ".claude"
PROMPT_MARKDOWN_PREFIX = ".config/opencode/"
PROMPT_MARKDOWN_NAMES = {"CLAUDE.md", "CLAUDE.local.md", "AGENTS.md"}
RUFF_FORMAT_COMMAND = "ruff format"
RUFF_HOOK_ID = "ruff"
RUFF_CHECK_HOOK_ID = "ruff-check"
RUFF_FORMAT_HOOK_ID = "ruff-format"
RUFF_CHECK_HOOK_IDS = (RUFF_HOOK_ID, RUFF_CHECK_HOOK_ID)
RUFF_HOOK_IDS = (*RUFF_CHECK_HOOK_IDS, RUFF_FORMAT_HOOK_ID)
PRE_COMMIT_CONFIG = ".pre-commit-config.yaml"
_RUFF_HOOK_ID_ALTERNATION = "|".join(re.escape(hook_id) for hook_id in RUFF_HOOK_IDS)
PRE_COMMIT_RUFF_HOOK = re.compile(
    rf"""^[ \t]*-?[ \t]*id:[ \t]*['"]?({_RUFF_HOOK_ID_ALTERNATION})['"]?(?:[ \t]+#.*)?[ \t\r]*$""")
# A line that ends the entry of the ruff hook above it: a list item that starts with a key (`- name:`, `- repo:`),
# any `id:` line, or a key at column 0.
PRE_COMMIT_ENTRY_START = re.compile(r"^(?:[ \t]*-[ \t]+[\w-]+:|[ \t]*id:|[^\s#])")
PRE_COMMIT_FILES_LINE = re.compile(r"^[ \t]*(?:-[ \t]+)?files:[ \t]*(.*?)[ \t\r]*$")
# An `exclude:` line: `indent` ends at the column of the key, which the lines of a block scalar value stand right of.
PRE_COMMIT_EXCLUDE_LINE = re.compile(r"^(?P<indent>[ \t]*(?:-[ \t]+)?)exclude:[ \t]*(?P<value>.*?)[ \t\r]*$")
PRE_COMMIT_TRAILING_COMMENT = re.compile(r"[ \t]+#.*$")
# The header of a YAML block scalar: literal `|` or folded `>`, then `-` when the last line break is cut.
PRE_COMMIT_BLOCK_HEADER = re.compile(r"^(?P<style>[|>])(?P<chomp>[+-]?)$")
QUOTE_CHARACTERS = ('"', "'")
# A `files:` value that starts with one of these (after one quote pair is stripped) is a block scalar, anchor, tag,
# flow collection or alias, or an unmatched quote, which no line match reads.
PRE_COMMIT_NON_PLAIN_FILES_STARTS = ('"', "'", "|", ">", "&", "!", "[", "{", "*", "#")
RUST_SUFFIX = ".rs"
RUSTFMT_COMMANDS = ("cargo fmt", "rustfmt")
RUSTFMT_CONFIG_FILES = ("rustfmt.toml", ".rustfmt.toml")
# rustfmt's own default is 2015, which cannot parse later syntax; cargo new has written 2021 or later since Rust 1.56.
DEFAULT_RUST_EDITION = "2021"
ESLINT_FLAT_CONFIG_FILES = ("eslint.config.js", "eslint.config.mjs", "eslint.config.cjs", "eslint.config.ts",
                            "eslint.config.mts", "eslint.config.cts")
# With this flag oxlint exits 0 when its ignore config leaves out every named file. Older releases reject it.
OXLINT_ALLOW_NO_FILES_FLAG = "--no-error-on-unmatched-pattern"
# What marks a repo as configuring a web tool: a config file at the repo root, or this key in its package.json.
WEB_TOOL_CONFIG_FILES = {
    "oxlint": (".oxlintrc.json", "oxlint.config.ts"),
    "eslint": (*ESLINT_FLAT_CONFIG_FILES, ".eslintrc", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json",
               ".eslintrc.yaml", ".eslintrc.yml"),
    "oxfmt": (".oxfmtrc.json", ".oxfmtrc.jsonc", "oxfmt.config.ts"),
    "prettier": (".prettierrc", ".prettierrc.json", ".prettierrc.yaml", ".prettierrc.yml", ".prettierrc.json5",
                 ".prettierrc.js", ".prettierrc.cjs", ".prettierrc.mjs", ".prettierrc.toml", "prettier.config.js",
                 "prettier.config.cjs", "prettier.config.mjs", "prettier.config.ts"),
}
WEB_TOOL_PACKAGE_KEYS = {"oxlint": "oxlint", "eslint": "eslintConfig", "oxfmt": "oxfmt", "prettier": "prettier"}


def run_quiet(command, repo):
    with contextlib.suppress(OSError):
        subprocess.run(command, cwd=repo, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)


def tool_available(repo, name):
    """True when the tool is on PATH or in the repo's node_modules/.bin."""
    return bool(shutil.which(name)) or locally_installed(repo, name)


def locally_installed(repo, name):
    local = os.path.join(repo, "node_modules", ".bin", name)
    return os.path.exists(local) and os.access(local, os.X_OK)


def tool_configured(repo, name):
    """True when the repo has the tool's config file, or a package.json key that configures it."""
    repo_path = pathlib.Path(repo)
    if any((repo_path / config).is_file() for config in WEB_TOOL_CONFIG_FILES[name]):
        return True

    package = repo_path / "package.json"
    if not package.is_file():
        return False

    try:
        manifest = json.loads(package.read_text(errors="replace"))
    except json.JSONDecodeError:
        return False
    return isinstance(manifest, dict) and WEB_TOOL_PACKAGE_KEYS[name] in manifest


def web_tool_enabled(repo, name):
    """True when the repo configures the tool or has it in node_modules/.bin."""
    return locally_installed(repo, name) or tool_configured(repo, name)


def first_lint_tool(use_oxlint, use_eslint):
    """"oxlint" when it is wanted, else "eslint" when that is, else None."""
    if use_oxlint:
        return "oxlint"
    if use_eslint:
        return "eslint"
    return None


def web_fix_tool(repo, configured_only=False):
    """"oxlint", "eslint" or None: the web linter whose `--fix` pass runs on the repo's script files. With
    `configured_only`, one the repo configures or has in node_modules/.bin, that can run: a configured linter that is
    not installed does not displace an installed one."""
    if configured_only:
        use_oxlint = web_tool_enabled(repo, "oxlint") and tool_available(repo, "oxlint")
        use_eslint = web_tool_enabled(repo, "eslint") and tool_available(repo, "eslint")
        return first_lint_tool(use_oxlint, use_eslint)

    return first_lint_tool(tool_available(repo, "oxlint"), locally_installed(repo, "eslint"))


def web_check_tool(repo):
    """"oxlint", "eslint" or None: the first web linter that the repo configures and that can run, for the check-mode
    lint of `lint_problems`."""
    use_oxlint = tool_configured(repo, "oxlint") and tool_available(repo, "oxlint")
    use_eslint = tool_configured(repo, "eslint") and tool_available(repo, "eslint")
    return first_lint_tool(use_oxlint, use_eslint)


def web_tool_launcher(repo, tool):
    """The repo's local binary, else the bare tool name for PATH. Never npx, which does not search PATH."""
    local_binary = os.path.join(repo, "node_modules", ".bin", tool)
    return [local_binary] if locally_installed(repo, tool) else [tool]


def web_lint_command(repo, tool, lint_files, fix):
    launcher = web_tool_launcher(repo, tool)
    fix_flags = ["--fix"] if fix else []
    if tool == "oxlint":
        # The fix pass does not read the exit code, so only the check asks oxlint what it accepts.
        ignore_flags = [] if fix else oxlint_ignore_flags(launcher, repo)
        return [*launcher, *fix_flags, *ignore_flags, *lint_files]
    if not uses_eslint_flat_config(repo):
        # Legacy .eslintrc mode rejects --no-warn-ignored, and with --max-warnings=0
        # the "file ignored" warning for an ignored file would exit 1.
        return [*launcher, *fix_flags, *lint_files]
    if not fix:
        # Check mode: only eslint errors are violations, as in eslint's own exit code that CI and pre-commit use.
        return [*launcher, "--no-warn-ignored", *lint_files]
    return [*launcher, *fix_flags, "--no-warn-ignored", "--max-warnings=0", *lint_files]


def oxlint_ignore_flags(launcher, repo):
    """[OXLINT_ALLOW_NO_FILES_FLAG] when this oxlint's --help lists the flag, else []."""
    _code, help_text = script_utils.run_command([*launcher, "--help"], repo, timeout=LINT_TIMEOUT_SECONDS)
    return [OXLINT_ALLOW_NO_FILES_FLAG] if OXLINT_ALLOW_NO_FILES_FLAG in help_text else []


def uses_eslint_flat_config(repo):
    """True when the repo root holds an eslint.config.* file."""
    repo_path = pathlib.Path(repo)
    return any((repo_path / config).is_file() for config in ESLINT_FLAT_CONFIG_FILES)


def web_lint_files(repo, tool, lint_files):
    """The `lint_files` the web linter `tool` is given. oxlint gets none that its ignore sources leave out: some
    releases lint such a file when it is named."""
    if tool != "oxlint":
        return lint_files
    ignored = oxlint_ignore.ignored_files(repo, lint_files)
    return [path for path in lint_files if path not in ignored]


def run_web_formatters(repo, lint_files, paths_to_format, configured_only=False):
    lint_tool = web_fix_tool(repo, configured_only) if lint_files else None
    tool_files = web_lint_files(repo, lint_tool, lint_files) if lint_tool else []
    if tool_files:
        run_quiet(web_lint_command(repo, lint_tool, tool_files, fix=True), repo)

    if not paths_to_format:
        return

    if configured_only:
        use_oxfmt = web_tool_enabled(repo, "oxfmt")
        use_prettier = web_tool_enabled(repo, "prettier")
    else:
        use_oxfmt = tool_available(repo, "oxfmt")
        use_prettier = True
    if use_oxfmt:
        run_quiet(["npx", "oxfmt", *paths_to_format], repo)
    elif use_prettier:
        run_quiet(["npx", "--yes", "prettier", "--write", *paths_to_format], repo)


class RuffHook:
    """A ruff hook entry of a .pre-commit-config.yaml: its id, its `files:` regex (None: every file) and its
    `exclude:` regex (None: no file)."""

    def __init__(self, hook_id):
        self.hook_id = hook_id
        self.files = None
        self.exclude = None

    def excludes(self, path):
        return regex_matches(self.exclude, path)

    def takes(self, path):
        """True when pre-commit hands the hook this file: `files:` matches it and `exclude:` does not."""
        if self.files is not None and not re.search(self.files, path):
            return False
        return not self.excludes(path)


class PreCommitConfig:
    """What the repo's .pre-commit-config.yaml says about ruff and about files no hook reads: its full text, its
    ruff hooks, and its top-level `exclude:` regex (None: no file)."""

    def __init__(self, text, ruff_hooks, exclude=None):
        self.text = text
        self.ruff_hooks = ruff_hooks
        self.exclude = exclude

    def hook_ids(self):
        return {hook.hook_id for hook in self.ruff_hooks}

    def excludes(self, path):
        return regex_matches(self.exclude, path)


def regex_matches(regex, path):
    """True when `regex` (None: matches no file) finds a match in `path`."""
    return regex is not None and bool(re.search(regex, path))


def files_value(line):
    """The regex of a `files:` line (see `plain_regex`); None when the line is no `files:` line or its value is one
    the line match cannot read, which means every file."""
    match = PRE_COMMIT_FILES_LINE.match(line)
    if not match:
        return None
    return plain_regex(match.group(1))


def plain_regex(raw_value):
    """The regex of a one-line `files:` or `exclude:` value, with its trailing comment and one matching pair of
    quotes stripped; None when the value is one the line match cannot read (empty, block-scalar, anchored, tagged or
    flow) or a regex that does not compile."""
    value = PRE_COMMIT_TRAILING_COMMENT.sub("", raw_value)
    if len(value) >= 2 and value[0] == value[-1] and value[0] in QUOTE_CHARACTERS:
        quote = value[0]
        value = value[1:-1]
        # A double-quoted YAML value decodes escapes, which this line match does not do.
        if quote == '"' and "\\" in value:
            return None
        if quote == "'":
            value = value.replace("''", "'")
    if not value or value.startswith(PRE_COMMIT_NON_PLAIN_FILES_STARTS):
        return None

    return compiled_or_none(value)


def compiled_or_none(regex):
    """The regex when it compiles, else None."""
    try:
        re.compile(regex)
    except re.error:
        return None
    return regex


def exclude_value(lines, index):
    """(column of the key, regex) for the `exclude:` line at `lines[index]`: a one-line value (see `plain_regex`) or
    a block scalar (`|` or `>`), whose text is the lines after it that stand right of the key. None when the line is
    no `exclude:` line; a regex of None when the value cannot be read, which excludes no file."""
    match = PRE_COMMIT_EXCLUDE_LINE.match(lines[index])
    if not match:
        return None

    key_column = len(match.group("indent"))
    header_text = PRE_COMMIT_TRAILING_COMMENT.sub("", match.group("value"))
    header = PRE_COMMIT_BLOCK_HEADER.match(header_text)
    if not header:
        return key_column, plain_regex(match.group("value"))

    body = []
    block_indent = None
    for line in lines[index + 1:]:
        line_indent = len(line) - len(line.lstrip(" "))
        if not line.strip():
            body.append("")
            continue
        if line_indent <= key_column:
            break
        # The first line sets the block's indent; a line indented further keeps the extra spaces, as in YAML.
        if block_indent is None:
            block_indent = line_indent
        body.append(line[block_indent:].rstrip())
    while body and not body[-1]:
        body.pop()
    if not body:
        return key_column, None

    text = "\n".join(body) if header.group("style") == "|" else fold_lines(body)
    # YAML keeps the last line break unless the header ends in `-`, and pre-commit matches with it in the regex.
    last_break = "" if header.group("chomp") == "-" else "\n"
    return key_column, compiled_or_none(text + last_break)


def fold_lines(body):
    """The text of a folded (`>`) block scalar's lines: neighbouring lines join with one space, and each blank line
    between two lines stays one line break, as YAML folds them. A line indented further than the block keeps the
    line break on each side of it."""
    text = ""
    blank_lines = 0
    previous_line = ""
    for line in body:
        if not line:
            blank_lines += 1
            continue
        kept_break = 1 if text and " " in (line[0], previous_line[0]) else 0
        if blank_lines or kept_break:
            text += "\n" * (blank_lines + kept_break)
        elif text:
            text += " "
        text += line
        blank_lines = 0
        previous_line = line
    return text


def top_level_exclude(config_text):
    """The regex of the config's top-level `exclude:` key, which no hook reads a matching file past; None when the
    config has none or it cannot be read."""
    lines = config_text.splitlines()
    for index in range(len(lines)):
        found = exclude_value(lines, index)
        if found is not None and found[0] == 0:
            return found[1]
    return None


def parse_ruff_hooks(config_text):
    """The ruff hooks of a .pre-commit-config.yaml text. The toolkit has no YAML parser, so each line is matched on
    its own: a hook entry runs from its `id:` line to the next list item that starts with a key, the next `id:`
    line or the next key at column 0 (`PRE_COMMIT_ENTRY_START`), a `files:` line after the `id:` line is the hook's
    regex, and an `exclude:` value after it (`exclude_value`) is the regex of the files the hook skips."""
    hooks = []
    current = None
    lines = config_text.splitlines()
    for index, line in enumerate(lines):
        if PRE_COMMIT_ENTRY_START.match(line):
            current = None
        id_match = PRE_COMMIT_RUFF_HOOK.match(line)
        if id_match:
            current = RuffHook(id_match.group(1))
            hooks.append(current)
            continue

        if current is None:
            continue

        files = files_value(line)
        if files is not None:
            current.files = files
        exclude = exclude_value(lines, index)
        if exclude is not None and exclude[1] is not None:
            current.exclude = exclude[1]
    return hooks


def read_pre_commit_config(repo):
    """The repo's pre-commit config as a PreCommitConfig; empty when the file is missing."""
    text = hook_input.read_file_text(pathlib.Path(repo) / PRE_COMMIT_CONFIG, "replace") or ""
    return PreCommitConfig(text, parse_ruff_hooks(text), top_level_exclude(text))


def repo_has_ruff_config_file(repo):
    """True when the repo has a ruff.toml, a .ruff.toml, or a pyproject.toml with a [tool.ruff] table."""
    repo_path = pathlib.Path(repo)
    if (repo_path / "ruff.toml").is_file() or (repo_path / ".ruff.toml").is_file():
        return True

    pyproject = read_toml(repo_path / "pyproject.toml")
    return "ruff" in pyproject.get("tool", {})


def repo_configures_ruff(repo):
    """True when the repo has a ruff config file (`repo_has_ruff_config_file`) or a .pre-commit-config.yaml hook
    with id ruff, ruff-check or ruff-format."""
    if repo_has_ruff_config_file(repo):
        return True
    return bool(read_pre_commit_config(repo).ruff_hooks)


def ruff_enabled(repo):
    """True when ruff is on PATH and the repo configures it."""
    return bool(shutil.which("ruff")) and repo_configures_ruff(repo)


def files_seen_by_hooks(hooks, hook_ids, python_files):
    """The `python_files` that at least one hook with an id in `hook_ids` takes (`RuffHook.takes`): its `files:`
    regex matches the file and its `exclude:` regex does not. When no hook has an id in `hook_ids`, no file: the
    command has no hook of its kind."""
    own_hooks = [hook for hook in hooks if hook.hook_id in hook_ids]
    return [path for path in python_files if any(hook.takes(path) for hook in own_hooks)]


def files_not_excluded_by_every_hook(hooks, hook_ids, python_files):
    """The `python_files` left after dropping each one that every hook with an id in `hook_ids` excludes. With no
    such hook, all of them."""
    own_hooks = [hook for hook in hooks if hook.hook_id in hook_ids]
    if not own_hooks:
        return list(python_files)
    return [path for path in python_files if not all(hook.excludes(path) for hook in own_hooks)]


# collections.namedtuple, not typing.NamedTuple: the Stop hook imports this module, and typing adds to its start-up.
RuffTargets = namedtuple("RuffTargets", ["format", "check"])


def ruff_targets(repo, python_files, pre_commit):
    """The Python files that `ruff format` and `ruff check` run on. With a ruff config file, all of them but the
    files that every ruff hook of the command's kind excludes (`files_not_excluded_by_every_hook`). When only
    pre-commit hooks enable ruff, the files that a ruff-format hook, and a ruff or ruff-check hook, take (see
    `files_seen_by_hooks`). `pre_commit` is the repo's PreCommitConfig."""
    hooks = pre_commit.ruff_hooks
    if repo_has_ruff_config_file(repo):
        return RuffTargets(files_not_excluded_by_every_hook(hooks, (RUFF_FORMAT_HOOK_ID,), python_files),
                           files_not_excluded_by_every_hook(hooks, RUFF_CHECK_HOOK_IDS, python_files))

    return RuffTargets(files_seen_by_hooks(hooks, (RUFF_FORMAT_HOOK_ID,), python_files),
                       files_seen_by_hooks(hooks, RUFF_CHECK_HOOK_IDS, python_files))


def repo_formats_with_ruff(repo, check_command=""):
    """True when the repo shows it formats with ruff: a [tool.ruff.format] table in pyproject.toml, a [format] table in
    ruff.toml or .ruff.toml, the hook id `ruff-format` or the text `ruff format` in .pre-commit-config.yaml, or
    `ruff format` named in the check command."""
    repo_path = pathlib.Path(repo)
    if RUFF_FORMAT_COMMAND in check_command:
        return True

    for name in ("ruff.toml", ".ruff.toml"):
        if "format" in read_toml(repo_path / name):
            return True

    pyproject = read_toml(repo_path / "pyproject.toml")
    if "format" in pyproject.get("tool", {}).get("ruff", {}):
        return True

    config = read_pre_commit_config(repo)
    return RUFF_FORMAT_HOOK_ID in config.hook_ids() or RUFF_FORMAT_COMMAND in config.text


def run_python_formatters(repo, python_files, pre_commit, configured_only=False, check_command=""):
    if not python_files or not ruff_enabled(repo):
        return

    targets = ruff_targets(repo, python_files, pre_commit)
    formats = not configured_only or repo_formats_with_ruff(repo, check_command)
    if formats and targets.format:
        run_quiet(["ruff", "format", "--force-exclude", *targets.format], repo)
    if targets.check:
        run_quiet(["ruff", "check", "--fix", "--force-exclude", *targets.check], repo)


def repo_formats_with_rustfmt(repo, check_command=""):
    """True when the repo shows it formats Rust with rustfmt: a rustfmt.toml or .rustfmt.toml at its root, or
    `cargo fmt` or `rustfmt` named in the check command."""
    repo_path = pathlib.Path(repo)
    if any(name in check_command for name in RUSTFMT_COMMANDS):
        return True
    return any((repo_path / name).is_file() for name in RUSTFMT_CONFIG_FILES)


def manifest_edition(manifest, key):
    """The edition string under `key` ("package" or "workspace.package") of a parsed Cargo.toml, or None."""
    table = manifest
    for part in key.split("."):
        table = table.get(part, {}) if isinstance(table, dict) else {}
    edition = table.get("edition") if isinstance(table, dict) else None
    return edition if isinstance(edition, str) else None


def rust_edition(repo, path):
    """The edition of the crate that holds `path`: the nearest Cargo.toml's [package] edition, else the nearest
    [workspace.package] edition at or above it inside the repo, else DEFAULT_RUST_EDITION."""
    root = pathlib.Path(repo).resolve()
    folder = (root / path).parent
    package_seen = False
    while folder == root or folder.is_relative_to(root):
        manifest = read_toml(folder / "Cargo.toml")
        if not package_seen and "package" in manifest:
            package_seen = True
            edition = manifest_edition(manifest, "package")
            if edition:
                return edition
        edition = manifest_edition(manifest, "workspace.package")
        if edition:
            return edition
        if folder == root:
            break
        folder = folder.parent
    return DEFAULT_RUST_EDITION


def run_rust_formatters(repo, rust_files, check_command=""):
    if not rust_files or not shutil.which("rustfmt") or not repo_formats_with_rustfmt(repo, check_command):
        return

    by_edition = {}
    for path in rust_files:
        edition = rust_edition(repo, path)
        by_edition.setdefault(edition, []).append(path)
    for edition, files in by_edition.items():
        run_quiet(["rustfmt", "--edition", edition, *files], repo)


def is_prompt_markdown(path):
    """True for a .md file a model reads as prompt text: under a .claude folder or .config/opencode/, or named
    CLAUDE.md, CLAUDE.local.md or AGENTS.md at any depth."""
    if not path.endswith(".md"):
        return False
    parts = pathlib.PurePosixPath(path).parts
    if PROMPT_MARKDOWN_DIR in parts[:-1] or parts[-1] in PROMPT_MARKDOWN_NAMES:
        return True
    return f"/{PROMPT_MARKDOWN_PREFIX}" in f"/{path}"


# collections.namedtuple, not typing.NamedTuple: the Stop hook imports this module, and typing adds to its start-up.
SortedFiles = namedtuple("SortedFiles", ["lint", "web", "python", "rust"])


def sort_files(repo, paths, include_python, pre_commit):
    """The existing files among `paths`, grouped by the tools that handle them. Leaves out docs/plans/ and prompt
    markdown, which a model reads literally, and each file the top-level `exclude:` of the repo's pre-commit config
    matches. `pre_commit` is the repo's PreCommitConfig."""
    sorted_files = SortedFiles([], [], [], [])
    for path in paths:
        if path.startswith(PLANS_DIR) or is_prompt_markdown(path) or not os.path.isfile(os.path.join(repo, path)):
            continue
        if pre_commit.excludes(path):
            continue
        add_to_groups(sorted_files, path, include_python)
    return sorted_files


def add_to_groups(sorted_files, path, include_python):
    if path.endswith(LINT_SUFFIXES):
        sorted_files.lint.append(path)
        sorted_files.web.append(path)
    elif path.endswith(FORMAT_ONLY_SUFFIXES):
        sorted_files.web.append(path)
    elif include_python and path.endswith(PYTHON_SUFFIX):
        sorted_files.python.append(path)
    elif path.endswith(RUST_SUFFIX):
        sorted_files.rust.append(path)


def lint_command_problem(command, repo):
    """[(command text, output)] when the command ran and exited non-zero or timed out, else []. Only a linter that
    cannot start (command not found) is exempt."""
    code, output = script_utils.run_command(command, repo, timeout=LINT_TIMEOUT_SECONDS)
    # Fail-open on purpose for a missing program only: nothing ran, so there is nothing to report. A timeout
    # is fail-closed: an unfinished lint is no proof the files are clean.
    if code in (0, script_utils.COMMAND_NOT_FOUND_EXIT_CODE):
        return []
    return [(" ".join(command), output)]


def lint_problems(repo, paths):
    """The lint violations the repo's configured linters report on the existing files among `paths`, as a list of
    (command text, output), one per linter that exited non-zero. Nothing is fixed. Python files go to
    `ruff check` when ruff is on PATH and the repo configures it (in a repo that configures ruff only through
    pre-commit hooks, only the files `ruff_targets` returns); web files go to the oxlint or eslint the repo
    configures and has installed (see `web_lint_files`). [] when every linter passes or none applies."""
    pre_commit = read_pre_commit_config(repo)
    files = sort_files(repo, paths, include_python=True, pre_commit=pre_commit)
    problems = []
    if files.python and ruff_enabled(repo):
        ruff_files = ruff_targets(repo, files.python, pre_commit).check
        if ruff_files:
            ruff_command = ["ruff", "check", "--force-exclude", "--output-format", "concise", *ruff_files]
            problems += lint_command_problem(ruff_command, repo)
    web_tool = web_check_tool(repo) if files.lint else None
    tool_files = web_lint_files(repo, web_tool, files.lint) if web_tool else []
    if tool_files:
        problems += lint_command_problem(web_lint_command(repo, web_tool, tool_files, fix=False), repo)
    return problems


def run_formatters(repo, paths, include_python=False, configured_only=False, check_command=""):
    """Run the autofix formatters on the existing files among `paths` (relative to `repo`), skipping docs/plans/ and
    prompt markdown (`is_prompt_markdown`): a model reads both literally, so a reflow changes what it does.
    Python files get `ruff format` and `ruff check --fix` only with `include_python`, when ruff is on PATH and the repo
    configures ruff (in a repo that configures ruff only through pre-commit hooks, only the files `ruff_targets`
    returns). With `configured_only`, a web linter runs only when the repo configures it and it can run,
    a web formatter only when the repo configures it or holds it in node_modules/.bin, and
    `ruff format` runs only when the repo shows it formats with ruff (`check_command` is the repo's check command).
    Rust files get `rustfmt` with their crate's edition when rustfmt is on PATH and the repo shows it formats with
    rustfmt (`repo_formats_with_rustfmt`).
    A missing tool is skipped silently. Returns the paths whose bytes changed."""
    pre_commit = read_pre_commit_config(repo)
    files = sort_files(repo, paths, include_python, pre_commit)
    candidates = files.web + files.python + files.rust
    root = pathlib.Path(repo)
    before = {path: file_hash(root, path) for path in candidates}

    run_web_formatters(repo, files.lint, files.web, configured_only)
    run_python_formatters(repo, files.python, pre_commit, configured_only, check_command)
    run_rust_formatters(repo, files.rust, check_command)

    return [path for path in candidates if file_hash(root, path) not in (before[path], UNREADABLE)]
