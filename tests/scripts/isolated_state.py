"""Keeps a test out of the real ~/.claude/state: the review-gate records and the hand-back
store live under it, and a test that reaches them with the real HOME adds its own rows to the live commit gate."""
import os
import pathlib
import tempfile
import unittest.mock

# The variables that name a state folder on their own, ahead of HOME. A value set outside the test could point at the
# real folder, so the test drops it and the scripts fall back to the HOME folder.
STATE_FOLDER_VARIABLES = ("HANDBACK_STORE_DIR",)


def isolate_state_root(test_case):
    """Point HOME at a temp folder for the length of `test_case`, in this process and in every child it starts, and
    drop the variables that name a state folder directly. Returns the temp HOME. A test that sets a state variable
    itself, after this call, still wins. Cleanup restores the environment, then removes the folder."""
    folder = tempfile.TemporaryDirectory(prefix="state-root-")
    test_case.addCleanup(folder.cleanup)
    home = pathlib.Path(folder.name)

    patcher = unittest.mock.patch.dict(os.environ, {"HOME": str(home)})
    patcher.start()
    test_case.addCleanup(patcher.stop)
    for name in STATE_FOLDER_VARIABLES:
        os.environ.pop(name, None)
    return home
