#!/bin/bash

# Read JSON input
input=$(cat)

# Extract all values in a single jq call
eval "$(echo "$input" | jq -r '
  @sh "cwd=\(.workspace.current_dir)",
  @sh "model_name=\(.model.display_name // "unknown")",
  @sh "context_size=\(.context_window.context_window_size // 0)",
  @sh "used_pct=\(.context_window.used_percentage // 0)",
  @sh "total_in=\(.context_window.total_input_tokens // 0)",
  @sh "total_out=\(.context_window.total_output_tokens // 0)",
  @sh "over_200k=\(.exceeds_200k_tokens // false)",
  @sh "five_hour_pct=\(.rate_limits.five_hour.used_percentage // empty)",
  @sh "five_hour_resets_at=\(.rate_limits.five_hour.resets_at // empty)",
  @sh "seven_day_pct=\(.rate_limits.seven_day.used_percentage // empty)",
  @sh "seven_day_resets_at=\(.rate_limits.seven_day.resets_at // empty)"
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

# Git info (skip the branch name when it duplicates the directory name, e.g. worktrees)
if git rev-parse --git-dir > /dev/null 2>&1; then
    branch=$(git branch --show-current 2>/dev/null)
    if [ "$branch" = "$dir_name" ]; then
        git_info=""
    else
        git_info=" git:($branch)"
    fi
else
    git_info=""
fi

# Build token info
# Prefer the real token count from the API response over the pct-derived
# estimate — used_percentage clamps at 100 when compaction lags the reported
# window (the 200k/200k pegged-display failure), so the real count is the
# only number that stays honest past the window size.
if [ "$context_size" -gt 0 ]; then
    tokens_used=$(( total_in + total_out ))
    if [ "$tokens_used" -gt 0 ]; then
        used_pct=$(( tokens_used * 100 / context_size ))
        [ "$used_pct" -gt 100 ] && used_pct=100
    else
        # Early in a session the API counts are absent; fall back to pct-derived.
        tokens_used=$(( context_size * used_pct / 100 ))
    fi
    remaining_pct=$(( 100 - used_pct ))

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

    over_warn=""
    if [ "$over_200k" = "true" ]; then
        over_warn=" ${RED}>200k${RESET}"
    fi

    token_info=$(printf " ${DIM}[${RESET}${pct_color}%s${RESET} %s${over_warn}${DIM}]${RESET}" "$bar" "$used_display")
else
    token_info=""
fi

# Rate-limit window segment: rate_limit_info <label> <used_pct> <resets_at_epoch>
rate_limit_info() {
    local label=$1 pct=$2 resets_at=$3
    [ -n "$pct" ] && [ -n "$resets_at" ] || return

    # Round used % to integer
    local pct_int
    pct_int=$(printf '%.0f' "$pct")

    # Time until reset
    local secs_left=$(( resets_at - $(date +%s) )) reset_display
    if [ "$secs_left" -lt 0 ]; then secs_left=0; fi
    if [ "$secs_left" -ge 86400 ]; then
        reset_display="$(( secs_left / 86400 ))d$(( (secs_left % 86400) / 3600 ))h"
    elif [ "$secs_left" -ge 3600 ]; then
        reset_display="$(( secs_left / 3600 ))h$(( (secs_left % 3600) / 60 ))m"
    elif [ "$secs_left" -ge 60 ]; then
        reset_display="$(( secs_left / 60 ))m"
    else
        reset_display="${secs_left}s"
    fi

    # Color-code by usage
    local color
    if [ "$pct_int" -ge 90 ]; then
        color=$RED
    elif [ "$pct_int" -ge 70 ]; then
        color=$YELLOW
    else
        color=$GREEN
    fi

    printf " ${DIM}[%s${RESET} ${color}%s%%${RESET} ${DIM}resets in${RESET} %s${DIM}]${RESET}" "$label" "$pct_int" "$reset_display"
}

five_hour_info=$(rate_limit_info "5h" "$five_hour_pct" "$five_hour_resets_at")
seven_day_info=$(rate_limit_info "wk" "$seven_day_pct" "$seven_day_resets_at")

# Two lines: model + branch/dir on top; context + rate limits below.
printf "${GREEN}➜${RESET} ${DIM}[${RESET}%s${DIM}]${RESET} ${CYAN}%s${RESET}%s\n%s%s%s" "$model_name" "$dir_name" "$git_info" "$token_info" "$five_hour_info" "$seven_day_info"
