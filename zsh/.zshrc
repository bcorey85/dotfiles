# Zsh plugins
autoload -Uz compinit && compinit
command -v zoxide &>/dev/null && eval "$(zoxide init zsh)"
command -v direnv &>/dev/null && eval "$(direnv hook zsh)"
source ~/.zsh/plugins/fzf-tab/fzf-tab.plugin.zsh
source ~/.zsh/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh
source ~/.zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh

# macOS runs ssh-agent via launchd; only start one on Linux
if [[ "$(uname)" != "Darwin" ]]; then
  eval "$(ssh-agent -s)" > /dev/null 2>&1
fi

function cdev() {
    project=$1
    base=~/dev

    if [ "$project" = "ps" ]
    then
        cd "$base/saitama"
    elif [ "$project" = "lf" ]
    then
        cd "$base/legalfit"
    elif [ "$project" = "st" ]
    then
        cd "$base/starfield"
    else
        cd "$base/$project"
    fi
}

function kill_port() {
    if [[ -n "$1" && "$1" =~ ^[0-9]+$ ]]; then
        lsof -t -i:$1 | xargs kill -9
        echo "Killing process running on port $1"
    else
        echo "Usage: kill_port <port_number>"
        echo "Error: Invalid or missing port number."
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
if command -v pyenv &>/dev/null; then
  export PYENV_ROOT="$HOME/.pyenv"
  export PATH="$PYENV_ROOT/bin:$PATH"
  eval "$(pyenv init --path)"
  eval "$(pyenv virtualenv-init -)"
fi

export PIPENV_VERBOSITY=-1
export PATH="/opt/homebrew/opt/node@18/bin:$PATH"

export GRPC_PYTHON_BUILD_SYSTEM_OPENSSL=1
export GRPC_PYTHON_BUILD_SYSTEM_ZLIB=1
if command -v brew &>/dev/null; then
  export LDFLAGS="-L$(brew --prefix zlib)/lib -L$(brew --prefix openssl)/lib\
 -L$(brew --prefix xz)/lib -L$(brew --prefix bzip2)/lib"
  export CPPFLAGS="-I$(brew --prefix zlib)/include -I$(brew --prefix openssl)/include\
 -I$(brew --prefix xz)/include -I$(brew --prefix bzip2)/include"
fi

export NVM_DIR="$HOME/.nvm"
  [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
  [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion
export PATH="/opt/homebrew/opt/openssl@3/bin:$PATH"

command -v starship &>/dev/null && eval "$(starship init zsh)"
command -v atuin &>/dev/null && eval "$(atuin init zsh)"


alias rl="source ~/.zshrc && clear && echo 'Reloaded .zshrc'"
alias zs='nvim ~/.zshrc'
alias vv='nvim ~/dotfiles'
alias gg="lazygit"
alias tt="tmux"
alias dd="lazydocker"
alias cc="claude"
alias cat="bat --plain"
alias ls="eza --icons"
alias ll="eza --icons -lha"
alias lt="eza --icons --tree --level=2"
command -v fd &>/dev/null || command -v fdfind &>/dev/null && alias fd="fdfind"
export FZF_DEFAULT_COMMAND='fd'

[[ "$TERM_PROGRAM" == "kiro" ]] && . "$(kiro --locate-shell-integration-path zsh)"
[[ -f /home/linuxbrew/.linuxbrew/bin/brew ]] && eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
export PATH="$HOME/.local/bin:$HOME:$PATH"

# SSH agent
if [[ "$(uname)" == "Linux" ]]; then
    eval "$(keychain --eval --quiet --agents ssh id_ed25519)"
fi

# bun completions
[ -s "/home/brandon/.bun/_bun" ] && source "/home/brandon/.bun/_bun"

# bun
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"
source "$HOME/.cargo/env"
