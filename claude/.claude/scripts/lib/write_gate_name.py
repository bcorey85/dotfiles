"""The name the Write gate (gates/fork_write_scope.py) and its unread-overwrite check (unread_overwrite.py) put at the
start of every stderr line they print. No imports: the Write gate loads this module on every Write, so it must stay
free of anything slow."""

GATE_NAME = "fork-write-scope"
