def process_exit_code(stopped, output):
    # The exit code a python3 process gives for this SystemExit; a message goes to `output`, as python3 prints it.
    if stopped.code is None:
        return 0
    if isinstance(stopped.code, int):
        return stopped.code
    output.write(f"{stopped.code}\n")
    return 1
