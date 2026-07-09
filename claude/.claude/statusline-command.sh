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
  @sh "five_hour_pct=\(.rate_limits.five_hour.used_percentage // empty)",
  @sh "five_hour_resets_at=\(.rate_limits.five_hour.resets_at // empty)"
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
# Derive remaining from used_pct so we don't depend on remaining_percentage
# being present (it's absent early in a session, which stranded the display at 0).
if [ "$context_size" -gt 0 ]; then
    remaining_pct=$(( 100 - used_pct ))

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

    token_info=$(printf " ${DIM}[${RESET}%s${DIM}]${RESET} ${DIM}[${RESET}${pct_color}%s${RESET} %s%% ${DIM}left |${RESET} %s${DIM}/${RESET}%s${DIM}]${RESET}" "$model_name" "$bar" "$remaining_pct" "$used_display" "$size_display")
else
    token_info=$(printf " ${DIM}[${RESET}%s${DIM}]${RESET}" "$model_name")
fi

# 5-hour rate-limit window
five_hour_info=""
if [ -n "$five_hour_pct" ] && [ -n "$five_hour_resets_at" ]; then
    # Round used % to integer
    five_h_int=$(printf '%.0f' "$five_hour_pct")

    # Time until reset
    now=$(date +%s)
    secs_left=$(( five_hour_resets_at - now ))
    if [ "$secs_left" -lt 0 ]; then secs_left=0; fi
    if [ "$secs_left" -ge 3600 ]; then
        h=$(( secs_left / 3600 ))
        m=$(( (secs_left % 3600) / 60 ))
        reset_display="${h}h${m}m"
    elif [ "$secs_left" -ge 60 ]; then
        reset_display="$(( secs_left / 60 ))m"
    else
        reset_display="${secs_left}s"
    fi

    # Color-code by usage
    if [ "$five_h_int" -ge 90 ]; then
        five_color=$RED
    elif [ "$five_h_int" -ge 70 ]; then
        five_color=$YELLOW
    else
        five_color=$GREEN
    fi

    five_hour_info=$(printf " ${DIM}[${RESET}${five_color}%s%%${RESET} ${DIM}resets in${RESET} %s${DIM}]${RESET}" "$five_h_int" "$reset_display")
fi

printf "${GREEN}➜${RESET} ${CYAN}%s${RESET}%s%s%s" "$dir_name" "$git_info" "$five_hour_info" "$token_info"
