"""Reads a TOML file on any Python the toolkit runs on. Python 3.10 has no tomllib, so there every TOML file reads as
empty, with one note on stderr, and each caller takes its no-config path."""
import sys

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None


def read_toml(path):
    """The file's TOML as a dict: {} when the file is missing, cannot be read, is not valid TOML, or this Python has no
    tomllib."""
    if not path.is_file():
        return {}

    if tomllib is None:
        version = f"{sys.version_info.major}.{sys.version_info.minor}"
        print(f"toml_file: Python {version} has no tomllib; {path} is read as empty", file=sys.stderr)
        return {}

    try:
        return tomllib.loads(path.read_text(errors="replace"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
