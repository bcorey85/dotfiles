# Dotfiles

Personal configuration files for Neovim, tmux, and zsh across WSL, Ubuntu, and macOS.

## What's Included

- **nvim** - Neovim configuration (LazyVim + custom plugins)
- **tmux** - tmux configuration with true color support
- **zsh** - zsh configuration

## Prerequisites

### WSL (Ubuntu)
```bash
sudo apt update
sudo apt install stow neovim tmux zsh git curl

# Install Nerd Font (on Windows side)
# Download from: https://github.com/ryanoasis/nerd-fonts/releases
# Install FiraCode Nerd Font or JetBrainsMono Nerd Font
# Configure Windows Terminal: Settings → Font face → "FiraCode Nerd Font"
```

### Ubuntu (Native)
```bash
sudo apt update
sudo apt install stow neovim tmux zsh git curl

# Install Nerd Font
mkdir -p ~/.local/share/fonts
cd ~/.local/share/fonts
curl -fLo "FiraCode Nerd Font.ttf" https://github.com/ryanoasis/nerd-fonts/raw/HEAD/patched-fonts/FiraCode/Regular/FiraCodeNerdFont-Regular.ttf
fc-cache -fv

# Configure terminal to use "FiraCode Nerd Font"
```

### macOS
```bash
# Install Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install stow neovim tmux zsh git
brew install --cask font-fira-code-nerd-font

# Configure terminal (iTerm2/Terminal.app) to use "FiraCode Nerd Font"
```

## Installation

### First Time Setup

```bash
# Clone this repo
git clone git@github.com:YOUR_USERNAME/dotfiles.git ~/dotfiles
cd ~/dotfiles

# Create symlinks (stow will skip any existing files)
stow nvim tmux zsh

# Restart your terminal or source zsh
source ~/.zshrc
```

### Platform-Specific Notes

**WSL:**
- Terminal runs on Windows, so install Nerd Fonts on Windows
- Configure Windows Terminal for best experience
- True color support requires tmux + terminal configuration

**Ubuntu:**
- Install fonts to `~/.local/share/fonts`
- Run `fc-cache -fv` after font installation
- Configure your terminal emulator's font settings

**macOS:**
- Use Homebrew for everything
- iTerm2 recommended for best terminal experience
- Terminal.app works but has fewer features

## Daily Workflow

```bash
# Edit configs normally - they're symlinked!
nvim ~/.config/nvim/lua/plugins/theme.lua
nvim ~/.tmux.conf
nvim ~/.zshrc

# Commit and push changes
cd ~/dotfiles
git add .
git commit -m "Update theme settings"
git push
```

## Updating on Another Machine

```bash
cd ~/dotfiles
git pull
# Changes are immediately available via symlinks!
```

## Uninstall

```bash
cd ~/dotfiles
stow -D nvim tmux zsh  # Removes symlinks
```

## Troubleshooting

**Icons not showing:**
- Install a Nerd Font
- Configure your terminal to use it
- Restart terminal

**Colors look wrong:**
- Check `echo $TERM` (should be `tmux-256color` in tmux)
- Verify true color support: `:checkhealth` in Neovim
- Ensure terminal emulator supports true colors

**Neovim plugins not loading:**
- Open Neovim and run `:Lazy sync`
- Check `:checkhealth` for issues

**Symlinks not working:**
- Ensure original configs are backed up/removed before running stow
- Check `ls -la ~` to verify symlinks point to `~/dotfiles/`
