"""Test support: whether this machine can run a capped systemd user scope, for tests that start a real one."""
import subprocess
import sys

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import memory_cap_scope


def systemd_scope_works():
    if not memory_cap_scope.cap_available():
        return False
    probe = subprocess.run(
        ["systemd-run", "--user", "--scope", "--quiet", "-p", "MemoryMax=64M", "-p", "MemorySwapMax=0", "true"],
        capture_output=True, timeout=30)
    return probe.returncode == 0
