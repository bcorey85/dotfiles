"""Which file paths count as source: not a test, a lockfile or a generated file."""

LOCKFILE_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock", "Cargo.lock",
                  "Gemfile.lock", "composer.lock", "go.sum", "bun.lockb"}


def is_test_path(path):
    lowered = path.lower()
    name = lowered.rsplit("/", 1)[-1]
    parts = lowered.split("/")[:-1]
    return (any(part in ("test", "tests", "__tests__", "spec", "specs") for part in parts)
            or name.startswith("test_") or ".test." in name or ".spec." in name or "_test." in name)


def is_uncounted_path(path):
    lowered = path.lower()
    name = lowered.rsplit("/", 1)[-1]
    return (path.rsplit("/", 1)[-1] in LOCKFILE_NAMES or name.endswith(".lock") or "__snapshots__" in lowered
            or name.endswith(".snap") or "generated" in lowered or ".generated." in name or ".gen." in name
            or name.endswith(".min.js") or "dist" in lowered.split("/")[:-1])


def is_counted_source(path):
    return not is_test_path(path) and not is_uncounted_path(path)
