"""Reads a repo's pytest options from the files pytest reads them from."""
import configparser
import contextlib
import pathlib
import re
import tomllib

DJANGO_SETTINGS = re.compile(r"DJANGO_SETTINGS_MODULE|--ds\b", re.IGNORECASE)

# The file and the section of it that holds the pytest options, outside pyproject.toml.
INI_SECTIONS = (("pytest.ini", "pytest"), ("tox.ini", "pytest"), ("setup.cfg", "tool:pytest"))


def pytest_options(repo_dir):
    """The pytest option tables of the repo, one dict per config file that has one: pyproject.toml
    [tool.pytest.ini_options] (values as TOML typed them), then the pytest section of pytest.ini, tox.ini and
    setup.cfg (values as strings, names lower-cased). A file that cannot be parsed has none."""
    repo_dir = pathlib.Path(repo_dir)
    tables = []

    pyproject = repo_dir / "pyproject.toml"
    if pyproject.is_file():
        try:
            options = tomllib.loads(pyproject.read_text()).get("tool", {}).get("pytest", {}).get("ini_options")
        except tomllib.TOMLDecodeError:
            options = None
        if isinstance(options, dict):
            tables.append(options)

    for name, section in INI_SECTIONS:
        config_file = repo_dir / name
        if not config_file.is_file():
            continue

        parser = configparser.ConfigParser(interpolation=None, strict=False)
        with contextlib.suppress(configparser.Error):
            parser.read_string(config_file.read_text())
        if parser.has_section(section):
            tables.append(dict(parser[section]))
    return tables


def has_django_settings(repo_dir):
    """True when pytest finds Django settings in the repo (DJANGO_SETTINGS_MODULE or the --ds option) in a pytest
    option table of pytest_options, or in the repo's conftest.py."""
    repo_dir = pathlib.Path(repo_dir)
    texts = [str(options) for options in pytest_options(repo_dir)]

    conftest = repo_dir / "conftest.py"
    if conftest.is_file():
        texts.append(conftest.read_text())
    return any(DJANGO_SETTINGS.search(text) for text in texts)
