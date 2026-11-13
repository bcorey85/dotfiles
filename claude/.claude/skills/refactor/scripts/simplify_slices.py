"""Slices of a simplify target: source files only, cut along module folders.

`plan_slices` drops test, index, style and generated files, groups the rest by the first folder below each target,
and packs whole groups into slices of at most `limit` files. A group over the limit splits by its own
subfolders the same way; a folder over the limit with no subfolders splits into sorted chunks.
"""
import os
from pathlib import PurePosixPath
from typing import NamedTuple

import source_paths

KIND_TEST = "test"
KIND_INDEX = "index"
KIND_STYLE = "style"
KIND_GENERATED = "generated"  # whatever source_paths.is_uncounted_path rejects
DROPPED_KINDS = (KIND_TEST, KIND_INDEX, KIND_STYLE, KIND_GENERATED)


class SliceError(Exception):
    """A tracked file that does not sit under the target it was listed for."""


class Slice(NamedTuple):
    files: list
    modules: list  # the module folders the slice holds, in slice order


class SlicePlan(NamedTuple):
    slices: list
    dropped: dict  # kind -> how many files were left out
    kept: int


class _Unit(NamedTuple):
    """Files that stay together in one slice, with the folder that names them."""
    folder: str
    files: list


def dropped_kind(path):
    """The kind of file that never counts toward a simplify slice, or "" for a source file."""
    if source_paths.is_test_path(path):
        return KIND_TEST
    if source_paths.is_index_file(path):
        return KIND_INDEX
    if source_paths.is_style_file(path):
        return KIND_STYLE
    if source_paths.is_uncounted_path(path):
        return KIND_GENERATED
    return ""


def dropped_summary(dropped):
    """`3 test, 1 index, 0 style, 0 generated`, in a fixed order."""
    return ", ".join(f"{dropped[kind]} {kind}" for kind in DROPPED_KINDS)


def plan_slices(files_by_target, limit):
    """files_by_target: (target, tracked files) pairs in the order given. A file in two targets counts once."""
    dropped = dict.fromkeys(DROPPED_KINDS, 0)
    units = []
    seen = set()
    for target, files in files_by_target:
        kept = _keep_source_files(files, seen, dropped)
        target_path = os.path.relpath(os.path.abspath(target))
        units += _target_units(target_path, sorted(kept), limit)
    slices = _pack(units, limit)
    kept_count = sum(len(unit.files) for unit in units)
    return SlicePlan(slices, dropped, kept_count)


def _keep_source_files(files, seen, dropped):
    """The source files not seen under an earlier target; counts each dropped file in `dropped`."""
    kept = []
    for path in files:
        if path in seen:
            continue
        seen.add(path)
        kind = dropped_kind(path)
        if kind:
            dropped[kind] += 1
            continue
        kept.append(path)
    return kept


def _target_units(target, files, limit):
    """The units of one target's kept files: the file itself, or its module folders."""
    if files == [target]:
        return [_Unit(target, files)]
    entries = [(path, _parts_below(target, path)) for path in files]
    return _folder_units(target, entries, limit)


def _parts_below(target, path):
    """The path parts under the target folder; a file outside it raises SliceError."""
    if target == ".":
        return PurePosixPath(path).parts
    prefix = target + "/"
    if not path.startswith(prefix):
        raise SliceError(f"{path} is not under target {target}")
    return PurePosixPath(path[len(prefix):]).parts


def _folder_units(folder, entries, limit):
    """Units for one folder's entries, (path, parts below the folder) pairs: a subfolder stays whole while it
    fits in a slice, and splits by its own subfolders when it does not."""
    groups = {}
    for path, parts in entries:
        groups.setdefault(parts[0], []).append((path, parts[1:]))
    if not any(len(parts) > 1 for _path, parts in entries):
        return _chunks(folder, [path for path, _parts in entries], limit)

    units = []
    for key in sorted(groups):
        group = groups[key]
        child = str(PurePosixPath(folder) / key)
        if not group[0][1]:
            units.append(_Unit(folder, [group[0][0]]))
        elif len(group) <= limit:
            units.append(_Unit(child, [path for path, _parts in group]))
        else:
            units += _folder_units(child, group, limit)
    return units


def _chunks(folder, files, limit):
    return [_Unit(folder, files[start:start + limit]) for start in range(0, len(files), limit)]


def _pack(units, limit):
    slices = []
    files = []
    modules = []
    for unit in units:
        if files and len(files) + len(unit.files) > limit:
            slices.append(Slice(files, modules))
            files, modules = [], []
        files += unit.files
        if unit.folder not in modules:
            modules.append(unit.folder)
    if files:
        slices.append(Slice(files, modules))
    return slices
