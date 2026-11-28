"""Usage: settings_hook.py add|remove <settings file> --event <Event> [--matcher <matcher>] --command <command>
                         [--if <condition>] [--timeout N] [--async]

Adds or removes one hook entry in a Claude settings file, touching no other byte, except that `remove` also
drops a group, event list or hooks object it leaves empty, so a `remove` after an `add` into an already-empty
one does not restore it.
The file must already be in the form `json.dumps(data, indent=2, ensure_ascii=False) + "\\n"` gives; any other form
exits 1 naming the file, unchanged.
--matcher is optional: when omitted, only groups with no "matcher" key match, and a new group gets none.
An entry is identified by its command and its --if value (both verbs).
`add` appends the entry to the first group of hooks[event] whose matcher equals --matcher, creating the event list or
the group at the end when missing. An entry with the same command and --if in any matching group prints
"already present" and writes nothing.
`remove` deletes the entry from every matching group, then each group it emptied, then the event key when empty, then
the hooks key when empty. An absent entry prints "absent" and writes nothing.
One line names what changed. Exit 0 on success or no-op, 1 on a refused file or a settings shape it cannot edit,
2 on a usage error.
"""
import argparse
import json
import pathlib
import sys
from typing import NoReturn

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent.parent / "lib")]
from script_utils import write_text_atomically


def parse_hook_arguments(argv):
    parser = argparse.ArgumentParser(description="Add or remove one hook entry in a settings file.")
    parser.add_argument("verb", choices=("add", "remove"))
    parser.add_argument("settings_file")
    parser.add_argument("--event", required=True)
    parser.add_argument("--matcher")
    parser.add_argument("--command", required=True)
    parser.add_argument("--if", dest="condition")
    parser.add_argument("--timeout", type=int)
    parser.add_argument("--async", dest="run_async", action="store_true")
    return parser.parse_args(argv)


def settings_text(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def fail(settings_file, reason) -> NoReturn:
    print(f"settings_hook: {settings_file}: {reason}", file=sys.stderr)
    sys.exit(1)


def load_settings(settings_file):
    """Return the parsed settings; stop unless re-rendering gives the file's exact text."""
    try:
        raw_text = pathlib.Path(settings_file).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        fail(settings_file, f"cannot read the file: {error}")
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as error:
        fail(settings_file, f"not valid JSON: {error}")
    if settings_text(data) != raw_text:
        fail(settings_file, 'refused: the file is not in the form json.dumps(indent=2, ensure_ascii=False) + "\\n" '
                            "gives, so an edit would change bytes beyond the entry; file left unchanged")
    return data


def hook_groups(settings_file, data, event, create):
    """The group list of `event`; None when missing and `create` is false."""
    if not isinstance(data, dict):
        fail(settings_file, "top level is not an object")
    hooks = data.get("hooks")
    if hooks is None:
        if not create:
            return None
        hooks = data["hooks"] = {}
    if not isinstance(hooks, dict):
        fail(settings_file, '"hooks" is not an object')
    groups = hooks.get(event)
    if groups is None:
        if not create:
            return None
        groups = hooks[event] = []
    if not isinstance(groups, list):
        fail(settings_file, f'hooks["{event}"] is not a list')
    return groups


def find_groups(groups, matcher):
    """Every group whose matcher equals `matcher`; None matches only groups with no matcher key."""
    dict_groups = [group for group in groups if isinstance(group, dict)]
    if matcher is None:
        return [group for group in dict_groups if "matcher" not in group]
    return [group for group in dict_groups if group.get("matcher") == matcher]


def matcher_text(matcher):
    return "no matcher" if matcher is None else f'matcher "{matcher}"'


def group_entries(settings_file, group):
    entries = group.get("hooks")
    if not isinstance(entries, list):
        fail(settings_file, f'the group for {matcher_text(group.get("matcher"))} has no "hooks" list')
    return entries


def new_entry(arguments):
    entry = {"type": "command", "command": arguments.command}
    if arguments.condition is not None:
        entry["if"] = arguments.condition
    if arguments.timeout is not None:
        entry["timeout"] = arguments.timeout
    if arguments.run_async:
        entry["async"] = True
    return entry


def is_target_entry(entry, arguments):
    """An entry is identified by its command and its `if` value."""
    return (isinstance(entry, dict) and entry.get("command") == arguments.command
            and entry.get("if") == arguments.condition)


def add_hook_entry(settings_file, data, arguments):
    """Return True when the entry was added, False when already present."""
    groups = hook_groups(settings_file, data, arguments.event, create=True)
    matching = find_groups(groups, arguments.matcher)
    requested = new_entry(arguments)
    for group in matching:
        entries = group_entries(settings_file, group)
        present = [entry for entry in entries if is_target_entry(entry, arguments)]
        if not present:
            continue
        if present[0] != requested:
            stored = json.dumps(present[0], ensure_ascii=False)
            wanted = json.dumps(requested, ensure_ascii=False)
            fail(settings_file, f"present as {stored}, not {wanted}; remove it first")
        return False
    if matching:
        first_entries = group_entries(settings_file, matching[0])
    else:
        group = {"hooks": []}
        if arguments.matcher is not None:
            group = {"matcher": arguments.matcher, "hooks": []}
        groups.append(group)
        first_entries = group["hooks"]
    first_entries.append(requested)
    return True


def remove_hook_entry(settings_file, data, arguments):
    """Return True when the entry was removed, False when absent."""
    groups = hook_groups(settings_file, data, arguments.event, create=False)
    if groups is None:
        return False
    removed = False
    emptied = []
    for group in find_groups(groups, arguments.matcher):
        entries = group_entries(settings_file, group)
        kept = [entry for entry in entries if not is_target_entry(entry, arguments)]
        if len(kept) == len(entries):
            continue
        removed = True
        entries[:] = kept
        if not entries:
            emptied.append(group)
    if not removed:
        return False
    # Drop by identity: list.remove would take the first group that merely equals an emptied one.
    groups[:] = [group for group in groups if not any(group is gone for gone in emptied)]
    if not groups:
        del data["hooks"][arguments.event]
    if not data["hooks"]:
        del data["hooks"]
    return True


def main(argv):
    arguments = parse_hook_arguments(argv)
    # Resolve a symlink so the atomic replace rewrites the target, not the link.
    settings_file = str(pathlib.Path(arguments.settings_file).resolve())
    data = load_settings(settings_file)
    description = f"event {arguments.event}, {matcher_text(arguments.matcher)}, command {arguments.command}"
    if arguments.condition is not None:
        description += f", if {arguments.condition}"
    if arguments.verb == "add":
        changed = add_hook_entry(settings_file, data, arguments)
        past_tense, no_op = "added", "already present"
    else:
        changed = remove_hook_entry(settings_file, data, arguments)
        past_tense, no_op = "removed", "absent"
    if not changed:
        print(f"{no_op}: {description}")
        return 0
    write_text_atomically(settings_file, settings_text(data).encode("utf-8"))
    print(f"{past_tense}: {description}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
