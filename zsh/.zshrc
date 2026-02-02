# If you come from bash you might have to change your $PATH.
# export PATH=$HOME/bin:/usr/local/bin:$PATH

# Path to your oh-my-zsh installation.
ZSH_DISABLE_COMPFIX=true
export ZSH="$HOME/.oh-my-zsh"

# Set name of the theme to load --- if set to "random", it will
# load a random theme each time oh-my-zsh is loaded, in which case,
# to know which specific one was loaded, run: echo $RANDOM_THEME
# See https://github.com/ohmyzsh/ohmyzsh/wiki/Themes

# ZSH_THEME="powerlevel10k/powerlevel10k"
# typeset -g POWERLEVEL9K_INSTANT_PROMPT=quiet

# Set list of themes to pick from when loading at random
# Setting this variable when ZSH_THEME=random will cause zsh to load
# a theme from this variable instead of looking in $ZSH/themes/
# If set to an empty array, this variable will have no effect.
# ZSH_THEME_RANDOM_CANDIDATES=( "robbyrussell" "agnoster" )

# Uncomment the following line to use case-sensitive completion.
# CASE_SENSITIVE="true"

# Uncomment the following line to use hyphen-insensitive completion.
# Case-sensitive completion must be off. _ and - will be interchangeable.
# HYPHEN_INSENSITIVE="true"

# Uncomment the following line to disable bi-weekly auto-update checks.
# DISABLE_AUTO_UPDATE="true"

# Uncomment the following line to automatically update without prompting.
# DISABLE_UPDATE_PROMPT="true"

# Uncomment the following line to change how often to auto-update (in days).
# export UPDATE_ZSH_DAYS=13

# Uncomment the following line if pasting URLs and other text is messed up.
# DISABLE_MAGIC_FUNCTIONS="true"

# Uncomment the following line to disable colors in ls.
# DISABLE_LS_COLORS="true"

# Uncomment the following line to disable auto-setting terminal title.
# DISABLE_AUTO_TITLE="true"

# Uncomment the following line to enable command auto-correction.
# ENABLE_CORRECTION="true"

# Uncomment the following line to display red dots whilst waiting for completion.
# COMPLETION_WAITING_DOTS="true"

# Uncomment the following line if you want to disable marking untracked files
# under VCS as dirty. This makes repository status check for large repositories
# much, much faster.
# DISABLE_UNTRACKED_FILES_DIRTY="true"

# Uncomment the following line if you want to change the command execution time
# stamp shown in the history command output.
# You can set one of the optional three formats:
# "mm/dd/yyyy"|"dd.mm.yyyy"|"yyyy-mm-dd"
# or set a custom format using the strftime function format specifications,
# see 'man strftime' for details.
# HIST_STAMPS="mm/dd/yyyy"

# Would you like to use another custom folder than $ZSH/custom?
# ZSH_CUSTOM=/path/to/new-custom-folder

# Which plugins would you like to load?
# Standard plugins can be found in $ZSH/plugins/
# Custom plugins may be added to $ZSH_CUSTOM/plugins/
# Example format: plugins=(rails git textmate ruby lighthouse)
# Add wisely, as too many plugins slow down shell startup.
plugins=(git zsh-syntax-highlighting zsh-autosuggestions)

source $ZSH/oh-my-zsh.sh

# User configuration

# export MANPATH="/usr/local/man:$MANPATH"

# You may need to manually set your language environment
# export LANG=en_US.UTF-8

# Preferred editor for local and remote sessions
# if [[ -n $SSH_CONNECTION ]]; then
#   export EDITOR='vim'
# else
#   export EDITOR='mvim'
# fi

# Compilation flags
# export ARCHFLAGS="-arch x86_64"

# Set personal aliases, overriding those provided by oh-my-zsh libs,
# plugins, and themes. Aliases can be placed here, though oh-my-zsh
# users are encouraged to define aliases within the ZSH_CUSTOM folder.
# For a full list of active aliases, run `alias`.
#
# Example aliases
# alias zshconfig="mate ~/.zshrc"
# alias ohmyzsh="mate ~/.oh-my-zsh"

alias yrw="yarn run watch"

function djc() {
    python manage.py init_client "$1"
    python manage.py switch_client "$1"

    if [ "$2" != "" ]
    then
        python manage.py load_client_data "$2"
    fi

    python manage.py runserver
}

function pro() {
    project=$1
    base=~/Desktop/dev

    if [ "$project" = "ps" ]
    then
        code "$base/saitama"
    elif [ "$project" = "lf" ]
    then
        code "$base/legalfit"
    elif [ "$project" = "st" ]
    then
        code "$base/starfield"
    else
        code "$base/$project"
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

alias rsd='./run_stencil_dev'
alias rwe='./run_watch_editor'
alias rds='./run_dev_server'
alias rfs='./run_frontend_server'
alias rtqa='./run_task_queue_all'

alias zshrc='code ~/.zshrc'

alias brew86="arch -x86_64 /usr/local/homebrew/bin/brew"
alias brewARM="/opt/homebrew/bin/brew"

alias reload="source ~/.zshrc && clear && echo 'Reloaded .zshrc'"
alias dev="cd ~/dev && ls"

export EDITOR='nvim'
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv virtualenv-init -)"

export PIPENV_VERBOSITY=-1
export PATH="/opt/homebrew/opt/node@18/bin:$PATH"

export GRPC_PYTHON_BUILD_SYSTEM_OPENSSL=1
export GRPC_PYTHON_BUILD_SYSTEM_ZLIB=1
export LDFLAGS="-L$(brew --prefix zlib)/lib -L$(brew --prefix openssl)/lib\
 -L$(brew --prefix xz)/lib -L$(brew --prefix bzip2)/lib"
export CPPFLAGS="-I$(brew --prefix zlib)/include -I$(brew --prefix openssl)/include\
 -I$(brew --prefix xz)/include -I$(brew --prefix bzip2)/include"

export NVM_DIR="$HOME/.nvm"
  [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
  [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion
export PATH="/opt/homebrew/opt/openssl@3/bin:$PATH"

eval "$(starship init zsh)"

export TERM=xterm-256color

alias lg="lazygit"
export FZF_DEFAULT_COMMAND='fd'

[[ "$TERM_PROGRAM" == "kiro" ]] && . "$(kiro --locate-shell-integration-path zsh)"
export PATH="/Users/legalfit/.local/bin:$PATH"
