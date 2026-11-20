"""The close pass's fix diff, read without touching the user's index.

`mark` records the tree of the work tree as it stands (the reviewed tree). `show` prints the diff command from that tree
to the work tree as it stands now, and the files it lists. Both build their tree in a scratch index. Run from the repo
root.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "scripts" / "lib"))
from script_utils import git_output, git_path, write_text_atomically
from worktree_snapshot import WorkTreeTreeError, work_tree_tree

STATE_FOLDER_NAME = "close-branch"
REVIEWED_TREE_NAME = "reviewed-tree"
USAGE = "usage: fix_diff.py mark | show"


def reviewed_tree_path(repo):
    path = git_path(repo, f"{STATE_FOLDER_NAME}/{REVIEWED_TREE_NAME}")
    if path is None:
        sys.exit(f"fix_diff.py: {repo} is not inside a git checkout")
    return path


def mark(repo):
    tree = work_tree_tree(repo)
    path = reviewed_tree_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomically(path, tree + "\n")
    print(tree)


def show(repo):
    path = reviewed_tree_path(repo)
    if not path.is_file():
        print(f"fix_diff.py: no reviewed tree recorded at {path}; run `fix_diff.py mark` first", file=sys.stderr)
        sys.exit(2)

    reviewed = path.read_text().strip()
    fixed = work_tree_tree(repo)
    names = git_output(repo, "diff", "--name-only", "--no-renames", reviewed, fixed)
    if names is None:
        sys.exit(f"fix_diff.py: `git diff --name-only --no-renames {reviewed} {fixed}` failed in {repo}")

    print(json.dumps({"reviewed_tree": reviewed, "fixed_tree": fixed,
                      "diff_command": f"git diff {reviewed} {fixed}", "files": names.splitlines()}))


VERBS = {"mark": mark, "show": show}


def main(argv):
    if len(argv) != 2 or argv[1] not in VERBS:
        sys.exit(USAGE)

    repo = pathlib.Path.cwd()
    run_verb = VERBS[argv[1]]
    try:
        run_verb(repo)
    except WorkTreeTreeError as error:
        sys.exit(f"fix_diff.py: {error}")


if __name__ == "__main__":
    main(sys.argv)
