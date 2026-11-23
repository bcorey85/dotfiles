"""oxlint_ignore.py: the files a repo's oxlint ignore sources leave out. The sources are `.eslintignore` and the
`ignorePatterns` of `.oxlintrc.json`, both at the repo root. Their patterns are gitignore patterns, so git matches
them. An oxlint.config.ts is not read: every oxlint that loads one skips a named file its patterns match."""
import json
import pathlib
import sys

import jsonc_text
import script_utils

ESLINT_IGNORE_FILE = ".eslintignore"
OXLINT_JSON_CONFIG = ".oxlintrc.json"


def config_ignore_patterns(repo):
    """The `ignorePatterns` strings of the repo's .oxlintrc.json. [] with no file, with no such list, or with a file
    that does not parse: oxlint reports that file itself."""
    config = pathlib.Path(repo) / OXLINT_JSON_CONFIG
    if not config.is_file():
        return []
    try:
        settings = jsonc_text.parse_jsonc(config.read_text(errors="replace"))
    except json.JSONDecodeError as error:
        # Fail-open on purpose: oxlint reports a config it cannot parse itself, so the hook only notes it.
        print(f"oxlint_ignore: {config} does not parse: {error}", file=sys.stderr)
        return []
    patterns = settings.get("ignorePatterns") if isinstance(settings, dict) else None
    if not isinstance(patterns, list):
        return []
    return [pattern for pattern in patterns if isinstance(pattern, str) and pattern]


def ignored_files(repo, paths):
    """The `paths` (relative to `repo`, the root of a git work tree) that the repo's oxlint ignore sources leave
    out, as a set."""
    exclude_options = [f"--exclude={pattern}" for pattern in config_ignore_patterns(repo)]
    if (pathlib.Path(repo) / ESLINT_IGNORE_FILE).is_file():
        exclude_options.append(f"--exclude-from={ESLINT_IGNORE_FILE}")
    if not exclude_options or not paths:
        return set()

    listing = script_utils.git_output(repo, "--literal-pathspecs", "ls-files", "-z", "--cached", "--others",
                                      "--ignored", *exclude_options, "--", *paths)
    # Fail-open on purpose: where git cannot match the patterns (no git, no work tree), oxlint gets every file and
    # applies its own ignore config.
    if listing is None:
        return set()
    return {path for path in listing.split("\0") if path}
