"""Test helpers: a throwaway git work tree, and full-check receipts planted in it through the receipt module."""
import pathlib
import subprocess
import sys
import tempfile

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import full_check_receipt

NO_RECEIPT_REASON = "No valid full-check receipt exists"


def make_repo(test, files=None):
    """A git work tree in a temp dir (deleted when `test` ends) holding `files` ({name: text}); returns its path."""
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    subprocess.run(["git", "init", "-q", tmp.name], check=True)
    for name, text in {"app.py": "x = 1\n", **(files or {})}.items():
        pathlib.Path(tmp.name, name).write_text(text)
    return tmp.name


def plant_receipt(repo, result="passed", satisfied=True, finish=True, steps=("npm test",)):
    """Write one full check run into the repo's receipts as full_check.py would, for the tree as it stands now."""
    run_id = full_check_receipt.write_started_row(repo, steps[0], " && ".join(steps))
    for index, step in enumerate(steps):
        full_check_receipt.write_step_row(repo, run_id, index, step, True, "whole")
    if finish:
        tree = full_check_receipt.current_tree(repo)
        full_check_receipt.write_finished_row(repo, run_id, result, 0, False, False, satisfied, tree, "")
    return run_id
