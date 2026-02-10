# Dotfiles

Personal configuration files across WSL, Ubuntu, and macOS.

## What's Included

- **nvim** - Neovim configuration (LazyVim + custom plugins)
- **tmux** - tmux configuration with true color support
- **zsh** - zsh configuration with oh-my-zsh
- **kitty** - Kitty terminal configuration
- **kanata** - Keyboard remapping
- **claude** - Claude Code configuration
- **scripts** - Utility scripts

## Quick Start

```bash
git clone git@github.com:bcorey85/dotfiles.git ~/dotfiles
cd ~/dotfiles
./setup ubuntu  # or: ./setup wsl | ./setup mac
```

The setup script handles everything: dependencies, fonts, symlinks, zsh plugins, starship prompt, and shell configuration.

## Individual Installers

Each step can also be run independently from the `install/` directory:

| Script                     | Args               | Description                                   |
| -------------------------- | ------------------ | --------------------------------------------- |
| `./install/deps`           | `wsl\|ubuntu\|mac` | System dependencies (apt/brew)                |
| `./install/fonts`          | `wsl\|ubuntu\|mac` | Nerd fonts                                    |
| `./install/stow`           |                    | Symlink configs via stow                      |
| `./install/zsh-plugins`    |                    | zsh-syntax-highlighting & zsh-autosuggestions |
| `./install/starship`       |                    | Starship prompt                               |
| `./install/claude-plugins` |                    | Claude Code plugins                           |
| `./install/zsh`            |                    | Set zsh as default shell                      |

## Daily Workflow

```bash
# Edit configs normally - they're symlinked
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
# Changes are immediately available via symlinks
```

## Uninstall

```bash
cd ~/dotfiles
stow -D nvim tmux zsh claude kitty kanata scripts
```

## Troubleshooting

**Icons not showing:**

- Install a Nerd Font (`./install/fonts ubuntu`)
- Configure your terminal to use it
- Restart terminal

**Colors look wrong:**

- Check `echo $TERM` (should be `tmux-256color` in tmux)
- Verify true color support: `:checkhealth` in Neovim

**Neovim plugins not loading:**

- Open Neovim and run `:Lazy sync`
- Check `:checkhealth` for issues

**Symlinks not working:**

- Ensure original configs are backed up/removed before running stow
- Check `ls -la ~` to verify symlinks point to `~/dotfiles/`
