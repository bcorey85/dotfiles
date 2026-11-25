"""The names of the stop files a /code fork writes into its run folder. No imports: the Write gate loads this module
on every code-fork Write, so it must stay free of anything slow."""

STOP_FILE = "stop.md"
REVIEW_STOP_FILE = "review-stop.md"
STOP_FILES = (STOP_FILE, REVIEW_STOP_FILE)
# Where phase_start moves a stale stop.md. Outside STOP_FILES: the relay reads it to exit 1 on a run that wrote no new
# stop, and relays it only once, as a bounced stop.md.
PREVIOUS_STOP_FILE = "stop.prev.md"
LOOP_DIR_FILE = "loop-dir"  # holds the path of the running loop's folder, where its reviewer requests go
PREVIOUS_LOOP_DIR_FILE = "loop-dir.prev"  # where phase_start.py moves the last phase's loop-dir
