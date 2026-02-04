#!/bin/bash

# Read JSON input
input=$(cat)

# Get current directory from JSON input
cwd=$(echo "$input" | jq -r '.workspace.current_dir')

# Change to the working directory
cd "$cwd" 2>/dev/null || cd ~

# Get basename of current directory
dir_name=$(basename "$cwd")

# Colors (dimmed for status line)
GREEN='\033[32m'
RED='\033[31m'
CYAN='\033[36m'
BLUE='\033[34m'
YELLOW='\033[33m'
RESET='\033[0m'

# Check if we're in a git repo
if git rev-parse --git-dir > /dev/null 2>&1; then
    branch=$(git branch --show-current 2>/dev/null)

    # Check if repo is dirty (using --no-optional-locks to avoid lock issues)
    if git --no-optional-locks diff-index --quiet HEAD -- 2>/dev/null; then
        # Clean
        git_info=" git:($branch)"
    else
        # Dirty
        git_info=" git:($branch) ✗"
    fi
else
    git_info=""
fi

# Get token usage information
total_input=$(echo "$input" | jq -r '.context_window.total_input_tokens // 0')
total_output=$(echo "$input" | jq -r '.context_window.total_output_tokens // 0')
context_size=$(echo "$input" | jq -r '.context_window.context_window_size // 0')
remaining_pct=$(echo "$input" | jq -r '.context_window.remaining_percentage // empty')

# Calculate total tokens used
tokens_used=$((total_input + total_output))

# Build token info string
if [ -n "$remaining_pct" ]; then
    # Format remaining percentage
    remaining_formatted=$(printf "%.1f" "$remaining_pct")
    token_info=$(printf " ${BLUE}[${RESET}${YELLOW}%s%%${RESET} ${BLUE}left | ${RESET}%s${BLUE}/${RESET}%s${BLUE}]${RESET}" "$remaining_formatted" "$tokens_used" "$context_size")
else
    # No messages yet
    token_info=$(printf " ${BLUE}[${RESET}0${BLUE}/${RESET}%s${BLUE}]${RESET}" "$context_size")
fi

# Build the prompt (without trailing arrow/dollar sign)
printf "${GREEN}➜${RESET} ${CYAN}%s${RESET}%s%s" "$dir_name" "$git_info" "$token_info"
