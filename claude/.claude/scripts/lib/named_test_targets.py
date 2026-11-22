"""named_test_targets.py: the test files and tests a set of shell commands runs by name, and whether each is still in a
tree. Takes plain commands and a repo folder; reads no module rule."""
import pathlib
import re

import check_scope


def named_targets(commands, repo):
    """The test targets the test commands name whose file and definition are present, in order, each once: a test
    file path, or a `file::name` node id."""
    targets = []
    for command in commands:
        for word in check_scope.named_test_targets(command):
            if target_is_missing(word, repo):
                continue
            if word not in targets:
                targets.append(word)
    return targets


def definition_pattern(name):
    """The text that defines a test or test class called `name` in Python, Rust or a JS test call."""
    escaped = re.escape(name)
    return re.compile(rf"""\b(?:def|fn|class)\s+{escaped}\b|\btest\(\s*['"`]{escaped}['"`]""")


def target_file(target):
    """The test file path of a target: the target itself, or the part before the first node of a node id."""
    return target.partition(check_scope.NODE_SEPARATOR)[0]


def target_is_missing(target, repo):
    """Whether the target's file is gone, or it names a test whose definition is absent from the file."""
    _path, _separator, nodes = target.partition(check_scope.NODE_SEPARATOR)
    test_file = pathlib.Path(repo) / target_file(target)
    if not test_file.is_file():
        return True
    if not nodes:
        return False
    # The last node is the test; a `[...]` suffix is a parameter set of it.
    name = nodes.split(check_scope.NODE_SEPARATOR)[-1].split("[")[0]
    return definition_pattern(name).search(test_file.read_text(errors="replace")) is None


def missing_targets(targets, repo):
    """The targets that are gone from the tree."""
    return [target for target in targets if target_is_missing(target, repo)]
