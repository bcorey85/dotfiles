#!/usr/bin/env bash
# PostToolUse hook: after three responses in a row that each made one read, in the main session or a coder, tell the
# model to batch.
# The logic lives in batch-reads-nudge.py beside this file.
exec python3 "$(dirname "$0")/batch-reads-nudge.py"
