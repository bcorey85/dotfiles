"""The repo's autofix formatters, run on a list of files: oxlint or eslint --fix and oxfmt or prettier for web and
document files, and (when asked) ruff for Python files. Any repo, any file list."""
import contextlib
import json
import os
import pathlib
import shutil
import subprocess

from toml_file import read_toml
from worktree_snapshot import UNREADABLE, file_hash

LINT_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".vue")
FORMAT_ONLY_SUFFIXES = (".json", ".css", ".scss", ".md")
PYTHON_SUFFIX = ".py"
PLANS_DIR = "docs/plans/"
PROMPT_MARKDOWN_DIR = ".claude"
PROMPT_MARKDOWN_PREFIX = ".config/opencode/"
PROMPT_MARKDOWN_NAMES = {"CLAUDE.md", "CLAUDE.local.md", "AGENTS.md"}
RUFF_FORMAT_COMMAND = "ruff format"
RUST_SUFFIX = ".rs"
RUSTFMT_COMMANDS = ("cargo fmt", "rustfmt")
RUSTFMT_CONFIG_FILES = ("rustfmt.toml", ".rustfmt.toml")
# rustfmt's own default is 2015, which cannot parse later syntax; cargo new has written 2021 or later since Rust 1.56.
DEFAULT_RUST_EDITION = "2021"
# What marks a repo as configuring a web tool: a config file at the repo root, or this key in its package.json.
WEB_TOOL_CONFIG_FILES = {
    "oxlint": (".oxlintrc.json", "oxlint.config.ts"),
    "eslint": ("eslint.config.js", "eslint.config.mjs", "eslint.config.cjs", "eslint.config.ts", "eslint.config.mts",
               "eslint.config.cts", ".eslintrc", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json", ".eslintrc.yaml",
               ".eslintrc.yml"),
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


def run_web_formatters(repo, lint_files, paths_to_format, configured_only=False):
    if lint_files:
        if configured_only:
            use_oxlint = web_tool_enabled(repo, "oxlint")
            use_eslint = web_tool_enabled(repo, "eslint")
        else:
            use_oxlint = tool_available(repo, "oxlint")
            use_eslint = locally_installed(repo, "eslint")
        if use_oxlint:
            run_quiet(["npx", "oxlint", "--fix", *lint_files], repo)
        elif use_eslint:
            run_quiet(["npx", "eslint", "--fix", "--no-warn-ignored", "--max-warnings=0", *lint_files], repo)

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


def repo_configures_ruff(repo):
    """True when the repo has a ruff.toml, a .ruff.toml, or a pyproject.toml with a [tool.ruff] table."""
    repo_path = pathlib.Path(repo)
    if (repo_path / "ruff.toml").is_file() or (repo_path / ".ruff.toml").is_file():
        return True

    pyproject = read_toml(repo_path / "pyproject.toml")
    return "ruff" in pyproject.get("tool", {})


def repo_formats_with_ruff(repo, check_command=""):
    """True when the repo shows it formats with ruff: a [tool.ruff.format] table in pyproject.toml, a [format] table in
    ruff.toml or .ruff.toml, or `ruff format` named in .pre-commit-config.yaml or the check command."""
    repo_path = pathlib.Path(repo)
    if RUFF_FORMAT_COMMAND in check_command:
        return True

    for name in ("ruff.toml", ".ruff.toml"):
        if "format" in read_toml(repo_path / name):
            return True

    pyproject = read_toml(repo_path / "pyproject.toml")
    if "format" in pyproject.get("tool", {}).get("ruff", {}):
        return True

    with contextlib.suppress(OSError):
        return RUFF_FORMAT_COMMAND in (repo_path / ".pre-commit-config.yaml").read_text(errors="replace")
    return False


def run_python_formatters(repo, python_files, configured_only=False, check_command=""):
    if not python_files or not shutil.which("ruff") or not repo_configures_ruff(repo):
        return

    if not configured_only or repo_formats_with_ruff(repo, check_command):
        run_quiet(["ruff", "format", *python_files], repo)
    run_quiet(["ruff", "check", "--fix", *python_files], repo)


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


def run_formatters(repo, paths, include_python=False, configured_only=False, check_command=""):
    """Run the autofix formatters on the existing files among `paths` (relative to `repo`), skipping docs/plans/ and
    prompt markdown (`is_prompt_markdown`): a model reads both literally, so a reflow changes what it does.
    Python files get `ruff format` and `ruff check --fix` only with `include_python`, when ruff is on PATH and the repo
    configures ruff. With
    `configured_only`, a web tool runs only when the repo configures it or holds it in node_modules/.bin, and
    `ruff format` runs only when the repo shows it formats with ruff (`check_command` is the repo's check command).
    Rust files get `rustfmt` with their crate's edition when rustfmt is on PATH and the repo shows it formats with
    rustfmt (`repo_formats_with_rustfmt`).
    A missing tool is skipped silently. Returns the paths whose bytes changed."""
    lint_files, web_files, python_files, rust_files = [], [], [], []
    for path in paths:
        if path.startswith(PLANS_DIR) or is_prompt_markdown(path) or not os.path.isfile(os.path.join(repo, path)):
            continue
        if path.endswith(LINT_SUFFIXES):
            lint_files.append(path)
            web_files.append(path)
        elif path.endswith(FORMAT_ONLY_SUFFIXES):
            web_files.append(path)
        elif include_python and path.endswith(PYTHON_SUFFIX):
            python_files.append(path)
        elif path.endswith(RUST_SUFFIX):
            rust_files.append(path)

    candidates = web_files + python_files + rust_files
    root = pathlib.Path(repo)
    before = {path: file_hash(root, path) for path in candidates}

    run_web_formatters(repo, lint_files, web_files, configured_only)
    run_python_formatters(repo, python_files, configured_only, check_command)
    run_rust_formatters(repo, rust_files, check_command)

    return [path for path in candidates if file_hash(root, path) not in (before[path], UNREADABLE)]
