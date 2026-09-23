#!/usr/bin/env bash
# PostToolUse hook: after three main-session responses in a row that each made one read, tell the model to batch.
# The logic lives in batch-reads-nudge.py beside this file.
exec python3 "$(dirname "$0")/batch-reads-nudge.py"
