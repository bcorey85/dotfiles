"""The names of the stop files a /code fork writes into its run folder. No imports: the Write gate loads this module
on every code-fork Write in a run folder, so it must stay free of anything slow."""

STOP_FILE = "stop.md"
REVIEW_STOP_FILE = "review-stop.md"
STOP_FILES = (STOP_FILE, REVIEW_STOP_FILE)
