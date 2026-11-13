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
import script_utils
from toml_file import read_toml
from worktree_snapshot import UNREADABLE, file_hash

LINT_TIMEOUT_SECONDS = 300
LINT_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".vue")
FORMAT_ONLY_SUFFIXES = (".json", ".css", ".scss", ".md")
PYTHON_SUFFIX = ".py"
PLANS_DIR = "docs/plans/"
PROMPT_MARKDOWN_DIR = ".claude"
PROMPT_MARKDOWN_PREFIX = ".config/opencode/"
PROMPT_MARKDOWN_NAMES = {"CLAUDE.md", "CLAUDE.local.md", "AGENTS.md"}
RUFF_FORMAT_COMMAND = "ruff format"
RUFF_FORMAT_HOOK_ID = "ruff-format"
PRE_COMMIT_CONFIG = ".pre-commit-config.yaml"
PRE_COMMIT_RUFF_HOOK = re.compile(
    r"""^[ \t]*-?[ \t]*id:[ \t]*['"]?(ruff|ruff-check|ruff-format)['"]?(?:[ \t]+#.*)?[ \t\r]*$""", re.MULTILINE)
RUST_SUFFIX = ".rs"
RUSTFMT_COMMANDS = ("cargo fmt", "rustfmt")
RUSTFMT_CONFIG_FILES = ("rustfmt.toml", ".rustfmt.toml")
# rustfmt's own default is 2015, which cannot parse later syntax; cargo new has written 2021 or later since Rust 1.56.
DEFAULT_RUST_EDITION = "2021"
ESLINT_FLAT_CONFIG_FILES = ("eslint.config.js", "eslint.config.mjs", "eslint.config.cjs", "eslint.config.ts",
                            "eslint.config.mts", "eslint.config.cts")
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
        return [*launcher, *fix_flags, *lint_files]
    if not uses_eslint_flat_config(repo):
        # Legacy .eslintrc mode rejects --no-warn-ignored, and with --max-warnings=0
        # the "file ignored" warning for an ignored file would exit 1.
        return [*launcher, *fix_flags, *lint_files]
    if not fix:
        # Check mode: only eslint errors are violations, as in eslint's own exit code that CI and pre-commit use.
        return [*launcher, "--no-warn-ignored", *lint_files]
    return [*launcher, *fix_flags, "--no-warn-ignored", "--max-warnings=0", *lint_files]


def uses_eslint_flat_config(repo):
    """True when the repo root holds an eslint.config.* file."""
    repo_path = pathlib.Path(repo)
    return any((repo_path / config).is_file() for config in ESLINT_FLAT_CONFIG_FILES)


def run_web_formatters(repo, lint_files, paths_to_format, configured_only=False):
    lint_tool = web_fix_tool(repo, configured_only) if lint_files else None
    if lint_tool:
        run_quiet(web_lint_command(repo, lint_tool, lint_files, fix=True), repo)

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


def pre_commit_ruff_hook_ids(config_text):
    """The ruff hook ids ("ruff", "ruff-check", "ruff-format") that a .pre-commit-config.yaml text names, as a
    set. The toolkit has no YAML parser, so each line is matched on its own."""
    return {match.group(1) for match in PRE_COMMIT_RUFF_HOOK.finditer(config_text)}


def repo_configures_ruff(repo):
    """True when the repo has a ruff.toml, a .ruff.toml, a pyproject.toml with a [tool.ruff] table, or a
    .pre-commit-config.yaml hook with id ruff, ruff-check or ruff-format."""
    repo_path = pathlib.Path(repo)
    if (repo_path / "ruff.toml").is_file() or (repo_path / ".ruff.toml").is_file():
        return True

    pyproject = read_toml(repo_path / "pyproject.toml")
    if "ruff" in pyproject.get("tool", {}):
        return True
    config_text = hook_input.read_file_text(repo_path / PRE_COMMIT_CONFIG, "replace") or ""
    return bool(pre_commit_ruff_hook_ids(config_text))


def ruff_enabled(repo):
    """True when ruff is on PATH and the repo configures it."""
    return bool(shutil.which("ruff")) and repo_configures_ruff(repo)


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

    config_text = hook_input.read_file_text(repo_path / PRE_COMMIT_CONFIG, "replace") or ""
    return RUFF_FORMAT_HOOK_ID in pre_commit_ruff_hook_ids(config_text) or RUFF_FORMAT_COMMAND in config_text


def run_python_formatters(repo, python_files, configured_only=False, check_command=""):
    if not python_files or not ruff_enabled(repo):
        return

    if not configured_only or repo_formats_with_ruff(repo, check_command):
        run_quiet(["ruff", "format", "--force-exclude", *python_files], repo)
    run_quiet(["ruff", "check", "--fix", "--force-exclude", *python_files], repo)


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


def sort_files(repo, paths, include_python):
    """The existing files among `paths`, grouped by the tools that handle them. Leaves out docs/plans/ and prompt
    markdown, which a model reads literally."""
    sorted_files = SortedFiles([], [], [], [])
    for path in paths:
        if path.startswith(PLANS_DIR) or is_prompt_markdown(path) or not os.path.isfile(os.path.join(repo, path)):
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
    `ruff check` when ruff is on PATH and the repo configures it; web files go to the oxlint or eslint the repo
    configures and has installed. [] when every linter passes or none applies."""
    files = sort_files(repo, paths, include_python=True)
    problems = []
    if files.python and ruff_enabled(repo):
        ruff_command = ["ruff", "check", "--force-exclude", "--output-format", "concise", *files.python]
        problems += lint_command_problem(ruff_command, repo)
    web_tool = web_check_tool(repo) if files.lint else None
    if web_tool:
        problems += lint_command_problem(web_lint_command(repo, web_tool, files.lint, fix=False), repo)
    return problems


def run_formatters(repo, paths, include_python=False, configured_only=False, check_command=""):
    """Run the autofix formatters on the existing files among `paths` (relative to `repo`), skipping docs/plans/ and
    prompt markdown (`is_prompt_markdown`): a model reads both literally, so a reflow changes what it does.
    Python files get `ruff format` and `ruff check --fix` only with `include_python`, when ruff is on PATH and the repo
    configures ruff. With
    `configured_only`, a web linter runs only when the repo configures it and it can run, a web formatter only when
    the repo configures it or holds it in node_modules/.bin, and
    `ruff format` runs only when the repo shows it formats with ruff (`check_command` is the repo's check command).
    Rust files get `rustfmt` with their crate's edition when rustfmt is on PATH and the repo shows it formats with
    rustfmt (`repo_formats_with_rustfmt`).
    A missing tool is skipped silently. Returns the paths whose bytes changed."""
    files = sort_files(repo, paths, include_python)
    candidates = files.web + files.python + files.rust
    root = pathlib.Path(repo)
    before = {path: file_hash(root, path) for path in candidates}

    run_web_formatters(repo, files.lint, files.web, configured_only)
    run_python_formatters(repo, files.python, configured_only, check_command)
    run_rust_formatters(repo, files.rust, check_command)

    return [path for path in candidates if file_hash(root, path) not in (before[path], UNREADABLE)]
