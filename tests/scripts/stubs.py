"""Executable stand-ins for the commands a script under test calls."""


def write_stub(path, body):
    path.write_text("#!/bin/bash\n" + body + "\n")
    path.chmod(0o755)
