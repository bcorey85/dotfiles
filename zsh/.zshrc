# Local overrides (not in repo)
[ -f ~/.zshrc.local ] && source ~/.zshrc.local

# ~/.local/bin before ANYTHING below: the multiplexer autostart is next, and the
# mux server it spawns hands its inherited PATH to every pane and popup command.
# Exported here rather than with the other PATH lines further down so popups can
# call hand-installed binaries (tuicr, herdr-*, dev scripts) by bare name — on
# Linux that prefix is where they live.
export PATH="$HOME/.local/bin:$HOME:$PATH"

# Auto-start a terminal multiplexer: herdr by default, tmux as the fallback on
# machines where herdr isn't installed (manual binary — see install/herdr). Both
# are attach-or-create: bare `herdr` restores its always-on persistent session;
# `tmux -A` reattaches `main`.
#   NO_MUX=1 (or legacy NO_TMUX=1)   escape hatch — bare terminal, no multiplexer
#   HERDR_* / $TMUX                  already inside a mux → skip, so a pane's
#                                    $SHELL never nests another mux.
if [ -z "$NO_MUX" ] && [ -z "$NO_TMUX" ] && [ -z "$TMUX" ] &&
  [ -z "${HERDR_TAB_ID}${HERDR_PANE_ID}${HERDR_SOCKET_PATH}" ]; then
  # herdr reads config.toml at server start, so the template must be rendered
  # BEFORE the launch below — not in the herdr block further down, which the
  # foreground `herdr` here doesn't reach until the session exits.
  if [ ! -f "$HOME/.config/herdr/config.toml" ] &&
    [ -f "$HOME/.config/herdr/config.toml.template" ]; then
    "$HOME/.local/bin/theme-mode" "$(cat "$HOME/.cache/theme-mode" 2>/dev/null || echo dark)" >/dev/null 2>&1 || true
  fi
  if [ -x "$HOME/.local/bin/herdr" ]; then
    "$HOME/.local/bin/herdr"
  elif command -v herdr &>/dev/null; then
    herdr
  elif command -v tmux &>/dev/null; then
    tmux new-session -A -s main
  fi
fi

# Repair a pane born with stdin detached from its pty. A tmux pane occasionally
# spawns having inherited the SERVER's fd 0 (/dev/null) instead of its own pty,
# while fd 1/2 wire up correctly. The prompt renders and tmux stays fully
# responsive (prefix keys, popups, window switching) but no keystroke can ever
# reach the shell — the window reads as frozen. /dev/tty is the controlling
# terminal, so this reattaches stdin to the right pty.
# Guarded on /dev/tty being readable: a failed exec redirect would leave every
# shell erroring at startup, which is worse than the freeze it repairs.
# Guarded on stdout being a tty because that is what separates the real failure
# (fd 0 detached, fd 1/2 on the pane's pty) from a tool-spawned shell, which has
# ALL THREE on pipes and is supposed to have no stdin. Without this the redirect
# fires on every agent/CI/script shell and hands it the terminal's keyboard, so
# anything reading stdin there silently eats the keystrokes you are typing.
if [[ -n "$TMUX" && ! -t 0 && -t 1 && -r /dev/tty ]]; then
  print -r -- "$(date -Iseconds) pane=$TMUX_PANE was=$(readlink /proc/$$/fd/0)" \
    >>~/.cache/tmux-stdin-repair.log 2>/dev/null
  exec </dev/tty
fi

# Zsh plugins
fpath=(~/.zsh/completions $fpath)
autoload -Uz compinit && compinit
command -v zoxide &>/dev/null && eval "$(zoxide init zsh)"
command -v direnv &>/dev/null && eval "$(direnv hook zsh)"
command -v mise &>/dev/null && eval "$(mise activate zsh)"
source ~/.zsh/plugins/fzf-tab/fzf-tab.plugin.zsh
source ~/.zsh/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh
autoload -Uz bracketed-paste-magic
zle -N bracketed-paste bracketed-paste-magic
source ~/.zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh


function kill_port() {
    if [[ -n "$1" && "$1" =~ ^[0-9]+$ ]]; then
        lsof -t -i:$1 | xargs kill -9
        echo "Killing process running on port $1"
    else
        echo "Usage: kill_port <port_number>"
        echo "Error: Invalid or missing port number."
    fi
}

# Bare `mprocs` only reads ./mprocs.yaml. When a repo has no local config, fall
# back to ~/.config/mprocs/projects/<dirname>.yaml (same lookup as ~/.local/bin/dev).
# Any args (incl. -c/--config or commands) bypass the fallback and pass through.
function mprocs() {
    if [[ $# -eq 0 && ! -f mprocs.yaml && -f "$HOME/.config/mprocs/projects/${PWD:t}.yaml" ]]; then
        command mprocs --config "$HOME/.config/mprocs/projects/${PWD:t}.yaml"
    else
        command mprocs "$@"
    fi
}

alias dj="python manage.py"
alias djlu="python manage.py load_users"
alias djrs="python manage.py runserver"
alias djic="python manage.py init_client"
alias djsc="python manage.py switch_client"
alias djlcd="python manage.py load_client_data"
alias djldb="python manage.py load_database"
alias djtqc="python manage.py task_queue_celery"

alias yrw="yarn run watch"

alias gcm='git checkout master'
alias gcb='git checkout -b'
alias gf="git fetch"
alias gmom="git merge origin/master"
alias grom="git rebase -i origin/master"
alias gpou='git push origin -u'
alias gpf='git push --force-with-lease'
alias ga='git add --all'
alias gcom='git commit -m'
alias gs='git switch'
alias gstat='git status'

# Git worktree helper: gwa <branch> [base-branch]
gwa() { git worktree add -b "$1" "../$1" "${2:-master}"; }

alias rsd='./run_stencil_dev'
alias rwe='./run_watch_editor'
alias rds='./run_dev_server'
alias rfs='./run_frontend_server'
alias rtqa='./run_task_queue_all'

alias brew86="arch -x86_64 /usr/local/homebrew/bin/brew"
alias brewARM="/opt/homebrew/bin/brew"

export EDITOR='nvim'
export VISUAL='nvim'
bindkey -e  # use emacs keybindings (ctrl+a/e/u) despite EDITOR=nvim
if command -v pyenv &>/dev/null; then
  export PYENV_ROOT="$HOME/.pyenv"
  export PATH="$PYENV_ROOT/bin:$PATH"
  eval "$(pyenv init --path)"
  eval "$(pyenv virtualenv-init -)"
fi

export PIPENV_VERBOSITY=-1
# node@18 pin (mac) — pre-mise fallback; with mise, per-project .nvmrc wins
command -v mise &>/dev/null || export PATH="/opt/homebrew/opt/node@18/bin:$PATH"

export GRPC_PYTHON_BUILD_SYSTEM_OPENSSL=1
export GRPC_PYTHON_BUILD_SYSTEM_ZLIB=1
if command -v brew &>/dev/null; then
  export LDFLAGS="-L$(brew --prefix zlib)/lib -L$(brew --prefix openssl)/lib\
 -L$(brew --prefix xz)/lib -L$(brew --prefix bzip2)/lib"
  export CPPFLAGS="-I$(brew --prefix zlib)/include -I$(brew --prefix openssl)/include\
 -I$(brew --prefix xz)/include -I$(brew --prefix bzip2)/include"
fi

# nvm fallback for machines without mise — mise owns node once installed
# (~300-700ms saved per shell; run install/mise before removing ~/.nvm)
if ! command -v mise &>/dev/null; then
  export NVM_DIR="$HOME/.nvm"
  [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
  [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
fi
export PATH="/opt/homebrew/opt/openssl@3/bin:$PATH"

# Starship: theme-mode regenerates the REAL ~/.config/starship.toml (starship's
# default path) with the active light/dark palette, so every running shell flips
# live on its next prompt — no STARSHIP_CONFIG, no reload. On a fresh machine
# (before theme-mode has ever run) that file doesn't exist yet, so bootstrap it
# from the stowed template with the dark palette baked in.
if command -v starship &>/dev/null; then
  if [ ! -f "$HOME/.config/starship.toml" ] && [ -f "$HOME/.config/starship.toml.template" ]; then
    sed 's/^palette = .*/palette = "dark"/' "$HOME/.config/starship.toml.template" >"$HOME/.config/starship.toml"
  fi
  eval "$(starship init zsh)"
fi

# herdr: the config.toml bootstrap lives in the multiplexer autostart at the top
# of this file — it has to run before the server starts, not here.
if command -v herdr &>/dev/null; then
  # herdr-automatic-rename shell hook: renames the tab the instant a command
  # starts. Without it naming waits for the next focus/tab event. No-op outside
  # a herdr pane; glob is (N) so a machine without the plugin skips silently.
  for _f in "$HOME"/.config/herdr/plugins/github/herdr-automatic-rename-*/shell/hook.zsh(N); do
    source "$_f"
    break
  done
fi


alias rl="source ~/.zshrc && clear && echo 'Reloaded .zshrc'"
alias vc='nvim +"cd ~/dotfiles" ~/dotfiles/zsh/.zshrc'
alias vv='nvim .'
alias vd='nvim +"cd ~/dotfiles" ~/dotfiles'
alias vn='nvim +"cd ~/vault" ~/vault'
alias nvim-old='NVIM_APPNAME=nvim-old nvim'
alias tt="tmux"
alias cc="claude"
alias oc="opencode"

# Machine-local overrides (secrets, paths, etc.)
[[ -f ~/.zshrc.local ]] && source ~/.zshrc.local

# cw [name] — worktree + agent cockpit. Creates .claude/worktrees/<name> off
# the current branch, copies untracked env files (.env*, .envrc — copied, never
# symlinked, so an agent editing one can't poison the other trees), then opens
# a dedicated tmux window running the nvim|claude dev split in the worktree.
# Outside tmux, falls back to the old cd + claude in place. Clean up with cwc.
function cw() {
    emulate -L zsh
    setopt null_glob
    local name="${1:-$(openssl rand -hex 4)}"
    local branch repo_root
    branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
    if [[ -z "$branch" ]]; then
        echo "Not in a git repo"
        return 1
    fi
    repo_root=$(git rev-parse --show-toplevel)
    local wt_dir="$repo_root/.claude/worktrees/$name"
    local wt_branch="worktree-$name"
    git -C "$repo_root" worktree add "$wt_dir" -b "$wt_branch" "$branch" || return 1

    # Env bootstrap — agents stall on a missing env; tracked files are already
    # in the worktree, so only copy what git didn't bring over.
    local f
    for f in "$repo_root"/.env "$repo_root"/.env.* "$repo_root"/.envrc; do
        [[ -f "$f" && ! -e "$wt_dir/${f:t}" ]] && cp "$f" "$wt_dir/${f:t}"
    done
    [[ -f "$wt_dir/.envrc" ]] && command -v direnv &>/dev/null && direnv allow "$wt_dir"

    if [[ -n "$TMUX" ]]; then
        # One cockpit window per worktree: nvim (60%) | claude (40%), named
        # after the worktree so the status line shows which agent lives where.
        tmux new-window -n "$name" -c "$wt_dir"
        tmux send-keys "nvim ." C-m
        tmux split-window -h -p 40 -c "$wt_dir"
        tmux send-keys "claude" C-m
        tmux select-pane -L
    else
        cd "$wt_dir" && claude
    fi
}

function cwc() {
    local repo_root
    repo_root=$(git worktree list --porcelain 2>/dev/null | head -1 | sed 's/^worktree //')
    if [[ -z "$repo_root" ]]; then
        echo "Not in a git repo"
        return 1
    fi
    local cwd="$PWD"
    local wt_dir="${cwd#$repo_root/}"
    if [[ "$wt_dir" == "$cwd" || ! "$wt_dir" == .claude/worktrees/* ]]; then
        echo "Not inside a .claude/worktrees/ worktree"
        echo "Current dir: $cwd"
        return 1
    fi
    local name="${wt_dir#.claude/worktrees/}"
    name="${name%%/*}"
    local wt_branch="worktree-$name"
    cd "$repo_root" || return 1
    git worktree remove ".claude/worktrees/$name" && echo "Removed worktree: $name"
    if git rev-parse --verify "$wt_branch" &>/dev/null; then
        read -q "reply?Delete branch $wt_branch? (y/n) "
        echo
        if [[ "$reply" == "y" ]]; then
            git branch -d "$wt_branch" 2>/dev/null || git branch -D "$wt_branch"
        fi
    fi
}
alias headroom-stats="grep 'Pipeline complete' /tmp/headroom.err | sed 's/.*: \([0-9,]*\) -> \([0-9,]*\) tokens.*/\1 \2/' | tr -d ',' | awk 'function fmt(v) {if(v>=1000000) return sprintf(\"%.1fM\",v/1000000); if(v>=1000) return sprintf(\"%.1fk\",v/1000); return v+0} {o+=\$1; c+=\$2; n++} END {s=o-c; pct=(o>0?s/o*100:0); printf \"requests:    %d\noriginal:    %s tokens\ncompressed:  %s tokens\nsaved:       %s tokens (%d%%)\n\n* Totals are cumulative per-request — the same\n  context is re-compressed each turn, so saved\n  tokens reflect total API billing reduction,\n  not unique content compressed.\n\", n, fmt(o), fmt(c), fmt(s), pct}'"
alias cat="bat --plain"
alias ls="eza --icons"
alias ll="eza --icons -lha"
alias lt="eza --icons --tree --level=2"
command -v fd &>/dev/null || { command -v fdfind &>/dev/null && alias fd="fdfind"; }
export FZF_DEFAULT_COMMAND='fd'

[[ "$TERM_PROGRAM" == "kiro" ]] && . "$(kiro --locate-shell-integration-path zsh)"
[[ -f /home/linuxbrew/.linuxbrew/bin/brew ]] && eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
# linuxbrew's shellenv prepends its own bin, so re-assert ~/.local/bin's priority
# (first set at the top of this file, ahead of the multiplexer autostart).
export PATH="$HOME/.local/bin:$HOME:$PATH"

# Flatpak desktop integration
command -v flatpak &>/dev/null && export XDG_DATA_DIRS="/var/lib/flatpak/exports/share:$HOME/.local/share/flatpak/exports/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"

# SSH agent
if [[ "$(uname)" == "Linux" ]] && command -v keychain &>/dev/null; then
    eval "$(keychain --eval --quiet id_ed25519)"
fi

# bun completions
[ -s "$HOME/.bun/_bun" ] && source "$HOME/.bun/_bun"

# bun
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"
# cargo — rustup.rs writes ~/.cargo/env; distro rustup packages do not, so
# fall back to putting the bin dir on PATH directly.
if [[ -f "$HOME/.cargo/env" ]]; then
  source "$HOME/.cargo/env"
elif [[ -d "$HOME/.cargo/bin" ]]; then
  export PATH="$HOME/.cargo/bin:$PATH"
fi

# Atuin — must be last to avoid hook conflicts
command -v atuin &>/dev/null && eval "$(atuin init zsh)"

# Added by sonarqube-cli installer
export PATH="$HOME/.local/share/sonarqube-cli/bin:$PATH"

# opencode
export PATH=/home/brandon/.opencode/bin:$PATH

# theme-mode wrapper: runs the real script (passing its output through), then
# sends OSC 12 to update the cursor color in the current terminal (ghostty
# reads this sequence; inside tmux the script sets cursor-colour itself).
# Output's last word is the mode ("<family> <mode>" from apply/status).
function theme-mode() {
  local out
  out=$("$HOME/.local/bin/theme-mode" "$@") || return 1
  [[ -n "$out" ]] && print -r -- "$out"
  local cursor="#ffffff"
  [[ "${out##* }" == "light" ]] && cursor="#000000"
  printf "\033]12;%s\007" "$cursor"
}
