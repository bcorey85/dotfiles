"""The repo's autofix formatters, run on a list of files: oxlint or eslint --fix and oxfmt or prettier for web and
document files, and (when asked) ruff for Python files. Any repo, any file list."""
import contextlib
import json
import os
import pathlib
import shutil
import subprocess
import tomllib

from worktree_snapshot import UNREADABLE, file_hash

LINT_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".vue")
FORMAT_ONLY_SUFFIXES = (".json", ".css", ".scss", ".md")
PYTHON_SUFFIX = ".py"
PLANS_DIR = "docs/plans/"
RUFF_FORMAT_COMMAND = "ruff format"
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

    pyproject = repo_path / "pyproject.toml"
    if not pyproject.is_file():
        return False

    try:
        return "ruff" in tomllib.loads(pyproject.read_text(errors="replace")).get("tool", {})
    except (OSError, tomllib.TOMLDecodeError):
        return False


def repo_formats_with_ruff(repo, check_command=""):
    """True when the repo shows it formats with ruff: a [tool.ruff.format] table in pyproject.toml, a [format] table in
    ruff.toml or .ruff.toml, or `ruff format` named in .pre-commit-config.yaml or the check command."""
    repo_path = pathlib.Path(repo)
    if RUFF_FORMAT_COMMAND in check_command:
        return True

    for name in ("ruff.toml", ".ruff.toml"):
        with contextlib.suppress(OSError, tomllib.TOMLDecodeError):
            if "format" in tomllib.loads((repo_path / name).read_text(errors="replace")):
                return True

    with contextlib.suppress(OSError, tomllib.TOMLDecodeError):
        pyproject = tomllib.loads((repo_path / "pyproject.toml").read_text(errors="replace"))
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


def run_formatters(repo, paths, include_python=False, configured_only=False, check_command=""):
    """Run the autofix formatters on the existing files among `paths` (relative to `repo`), skipping docs/plans/.
    Python files get `ruff format` and `ruff check --fix` only with `include_python`, when ruff is on PATH and the repo
    configures ruff. With
    `configured_only`, a web tool runs only when the repo configures it or holds it in node_modules/.bin, and
    `ruff format` runs only when the repo shows it formats with ruff (`check_command` is the repo's check command).
    A missing tool is skipped silently. Returns the paths whose bytes changed."""
    lint_files, web_files, python_files = [], [], []
    for path in paths:
        if path.startswith(PLANS_DIR) or not os.path.isfile(os.path.join(repo, path)):
            continue
        if path.endswith(LINT_SUFFIXES):
            lint_files.append(path)
            web_files.append(path)
        elif path.endswith(FORMAT_ONLY_SUFFIXES):
            web_files.append(path)
        elif include_python and path.endswith(PYTHON_SUFFIX):
            python_files.append(path)

    candidates = web_files + python_files
    root = pathlib.Path(repo)
    before = {path: file_hash(root, path) for path in candidates}

    run_web_formatters(repo, lint_files, web_files, configured_only)
    run_python_formatters(repo, python_files, configured_only, check_command)

    return [path for path in candidates if file_hash(root, path) not in (before[path], UNREADABLE)]
