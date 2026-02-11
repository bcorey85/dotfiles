#!/bin/bash

# Read JSON input
input=$(cat)

# Extract all values in a single jq call
eval "$(echo "$input" | jq -r '
  @sh "cwd=\(.workspace.current_dir)",
  @sh "model_name=\(.model.display_name // "unknown")",
  @sh "context_size=\(.context_window.context_window_size // 0)",
  @sh "used_pct=\(.context_window.used_percentage // 0)",
  @sh "remaining_pct=\(.context_window.remaining_percentage // empty)",
  @sh "total_cost=\(.cost.total_cost_usd // 0)",
  @sh "total_duration_ms=\(.cost.total_duration_ms // 0)",
  @sh "lines_added=\(.cost.total_lines_added // 0)",
  @sh "lines_removed=\(.cost.total_lines_removed // 0)",
  @sh "cache_read=\(.context_window.current_usage.cache_read_input_tokens // 0)",
  @sh "cache_create=\(.context_window.current_usage.cache_creation_input_tokens // 0)",
  @sh "fresh_input=\(.context_window.current_usage.input_tokens // 0)"
')"

# Change to the working directory
cd "$cwd" 2>/dev/null || cd ~
dir_name=$(basename "$cwd")

# Colors
GREEN='\033[32m'
RED='\033[31m'
CYAN='\033[36m'
BLUE='\033[34m'
YELLOW='\033[33m'
DIM='\033[2m'
RESET='\033[0m'

# Git info
if git rev-parse --git-dir > /dev/null 2>&1; then
    branch=$(git branch --show-current 2>/dev/null)
    if git --no-optional-locks diff-index --quiet HEAD -- 2>/dev/null; then
        git_info=" git:($branch)"
    else
        git_info=" git:($branch) ✗"
    fi
else
    git_info=""
fi

# Build token info
if [ -n "$remaining_pct" ]; then
    # Calculate tokens used from percentage
    tokens_used=$(( context_size * used_pct / 100 ))

    # Human-readable token counts (e.g., 108k/200k)
    if [ "$tokens_used" -ge 1000 ]; then
        used_display="$((tokens_used / 1000))k"
    else
        used_display="$tokens_used"
    fi
    if [ "$context_size" -ge 1000 ]; then
        size_display="$((context_size / 1000))k"
    else
        size_display="$context_size"
    fi

    # Color code remaining percentage
    if [ "$remaining_pct" -gt 50 ]; then
        pct_color=$GREEN
    elif [ "$remaining_pct" -gt 25 ]; then
        pct_color=$YELLOW
    else
        pct_color=$RED
    fi

    # Build visual bar (10 chars wide)
    bar_width=10
    filled=$(( used_pct * bar_width / 100 ))
    empty=$(( bar_width - filled ))
    bar=""
    for ((i=0; i<filled; i++)); do bar+="█"; done
    for ((i=0; i<empty; i++)); do bar+="░"; done

    # Format cost
    cost_display=$(printf "≈\$%.2f" "$total_cost")

    # Cache efficiency
    cache_total=$(( cache_read + cache_create + fresh_input ))
    if [ "$cache_total" -gt 0 ]; then
        cache_pct=$(( cache_read * 100 / cache_total ))
    else
        cache_pct=0
    fi

    # Format lines changed
    lines_info=""
    if [ "$lines_added" -gt 0 ] || [ "$lines_removed" -gt 0 ]; then
        lines_info=$(printf " ${DIM}[${RESET}${GREEN}+%s${RESET} ${RED}-%s${RESET}${DIM}]${RESET}" "$lines_added" "$lines_removed")
    fi

    # Format session duration
    total_seconds=$(( total_duration_ms / 1000 ))
    if [ "$total_seconds" -ge 3600 ]; then
        hours=$(( total_seconds / 3600 ))
        mins=$(( (total_seconds % 3600) / 60 ))
        duration_display="${hours}h${mins}m"
    elif [ "$total_seconds" -ge 60 ]; then
        mins=$(( total_seconds / 60 ))
        duration_display="${mins}m"
    else
        duration_display="${total_seconds}s"
    fi

    token_info=$(printf " ${DIM}[${RESET}%s${DIM}]${RESET} ${DIM}[${RESET}${pct_color}%s${RESET} %s%% ${DIM}left |${RESET} %s${DIM}/${RESET}%s${DIM}]${RESET} ${DIM}[${RESET}%s${DIM}]${RESET}%s ${DIM}[${RESET}⚡%s%% cached${DIM}]${RESET} ${DIM}[${RESET}%s${DIM}]${RESET}" "$model_name" "$bar" "$remaining_pct" "$used_display" "$size_display" "$cost_display" "$lines_info" "$cache_pct" "$duration_display")
else
    token_info=$(printf " ${DIM}[${RESET}%s${DIM}]${RESET} ${DIM}[${RESET}0${DIM}/${RESET}%s${DIM}]${RESET}" "$model_name" "$context_size")
fi

printf "${GREEN}➜${RESET} ${CYAN}%s${RESET}%s%s" "$dir_name" "$git_info" "$token_info"
