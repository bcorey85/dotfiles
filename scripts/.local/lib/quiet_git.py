"""A git runner that never prompts and never writes optional index files, shared by the lane scripts."""
import os
import subprocess


def run_quiet_git(folder, *args, timeout=None, errors=None):
    """Run git in `folder` (the working directory when None) and return the finished process.

    A git that cannot start raises OSError; one that outlives `timeout` raises subprocess.TimeoutExpired.
    """
    # No credential prompt: the lane scripts also run under a popup or a timer that has nobody to answer.
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    command = ["git"] if folder is None else ["git", "-C", str(folder)]
    return subprocess.run([*command, *args], capture_output=True, text=True, errors=errors, timeout=timeout, env=env)
