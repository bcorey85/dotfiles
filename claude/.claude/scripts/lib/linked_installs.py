"""linked_installs.py — whether a repo's dependency folders link back into the repo itself.

A check run on a copy of the repo through such a link would load the repo's own files, not the copy's.
"""

import json
import os
import pathlib
import urllib.parse

import script_utils

# The folders a repo keeps a Python virtualenv in.
VENV_FOLDERS = (".venv", "venv")
# Environment variables whose entries put code on the interpreter's import path.
IMPORT_PATH_VARIABLES = ("PYTHONPATH", "NODE_PATH")


def site_packages_of(prefix):
    return [*prefix.glob("lib*/python*/site-packages"), prefix / "Lib" / "site-packages"]


def import_path_enters_repo(env, own_paths, repo_path):
    """True when an entry of the PYTHONPATH or NODE_PATH the check inherits (os.environ when `env` is None) resolves
    inside the repo: the base run would import the head tree's code."""
    inherited = os.environ if env is None else env
    roots = [pathlib.Path(path).resolve() for path in own_paths]
    for variable in IMPORT_PATH_VARIABLES:
        for entry in inherited.get(variable, "").split(os.pathsep):
            if not entry:
                continue
            resolved = (repo_path / entry).resolve()
            if any(resolved == tree_root or tree_root in resolved.parents for tree_root in roots):
                return True
    return False


def names_path_inside(entry, repo_spellings):
    """True when the file's text names a path inside the repo, under any of its spellings."""
    if not entry.is_file():
        return False

    text = entry.read_text(errors="replace")
    return any(script_utils.names_path(spelling, text) for spelling in repo_spellings)


def is_editable_entry(entry, repo_path, inside_only, repo_spellings):
    """True when the site-packages entry is an editable or linked install; with `inside_only`, only one that points
    inside the repo."""
    if entry.name.endswith(".dist-info"):
        return is_editable_dist_info(entry, repo_path if inside_only else None)
    if entry.name.startswith("__editable__") or entry.name.endswith(".egg-link"):
        return not inside_only or names_path_inside(entry, repo_spellings)
    return inside_only and entry.name.endswith(".pth") and names_path_inside(entry, repo_spellings)


def holds_editable_install(repo_path, env=None, repo_spellings=None):
    """True when a .venv or venv of the repo holds an editable or linked install, when the virtualenv or conda
    environment named by `env` (VIRTUAL_ENV, CONDA_PREFIX) holds one that points inside the repo, or when a
    node_modules holds a symlink that resolves inside the repo: a base run through the links would load the diff's own
    files. `repo_spellings` are the path strings that name the repo (the resolved path and the one the caller was
    given, which differ under a symlinked folder); it defaults to the resolved path alone."""
    env = os.environ if env is None else env
    given_path = pathlib.Path(repo_path).absolute()
    repo_path = given_path.resolve()
    if repo_spellings is None:
        repo_spellings = tuple(dict.fromkeys((str(repo_path), str(given_path))))
    prefixes = [(repo_path / folder, False) for folder in VENV_FOLDERS]
    prefixes += [(pathlib.Path(env[name]), True) for name in ("VIRTUAL_ENV", "CONDA_PREFIX") if env.get(name)]
    for prefix, inside_only in prefixes:
        for site in site_packages_of(prefix):
            if not site.is_dir():
                continue
            if any(is_editable_entry(entry, repo_path, inside_only, repo_spellings) for entry in site.iterdir()):
                return True

    modules = repo_path / "node_modules"
    if not modules.is_dir():
        return False

    for entry in [*modules.iterdir(), *modules.glob("@*/*")]:
        if not entry.is_symlink():
            continue
        target = entry.resolve()
        if target.is_relative_to(repo_path) and not target.is_relative_to(modules.resolve()):
            return True
    return False


def is_editable_dist_info(dist_info, repo_path=None):
    """True when the dist-info's direct_url.json marks an editable install; with `repo_path`, only one whose url
    points inside it."""
    direct_url = dist_info / "direct_url.json"
    if not direct_url.is_file():
        return False

    try:
        recorded = json.loads(direct_url.read_text(errors="replace"))
        if not recorded.get("dir_info", {}).get("editable"):
            return False
        if repo_path is None:
            return True

        parsed_url = urllib.parse.urlparse(recorded.get("url", ""))
        url_path = urllib.parse.unquote(parsed_url.path)
        install_path = pathlib.Path(url_path).resolve()
        return install_path.is_relative_to(repo_path)
    except (ValueError, AttributeError):
        return False
