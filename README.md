# Dotfiles

Personal configuration files across WSL, Ubuntu, macOS, and Arch Linux.

## What's Included

- **nvim** - Neovim configuration (native `vim.pack`, specs in `lua/plugins/`)
- **tmux** - tmux configuration with true color support
- **zsh** - zsh configuration (manually cloned plugins, starship prompt)
- **kanata** - Keyboard remapping
- **claude** - Claude Code configuration
- **scripts** - Utility scripts

## Quick Start

```bash
git clone git@github.com:bcorey85/dotfiles.git ~/dotfiles
cd ~/dotfiles
./setup ubuntu  # or: ./setup wsl | ./setup mac | ./setup arch
```

The setup script handles everything: dependencies, fonts, symlinks, zsh plugins, starship prompt, and shell configuration.

## Individual Installers

Each step can also be run independently from the `install/` directory:

| Script                     | Args                     | Description                                   |
| -------------------------- | ------------------------ | --------------------------------------------- |
| `./install/deps`           | `wsl\|ubuntu\|mac\|arch` | System dependencies (apt/brew/pacman)         |
| `./install/fonts`          | `wsl\|ubuntu\|mac\|arch` | Nerd fonts                                    |
| `./install/stow`           |                          | Symlink configs via stow                      |
| `./install/zsh-plugins`    |                          | zsh-syntax-highlighting & zsh-autosuggestions |
| `./install/starship`       |                          | Starship prompt                               |
| `./install/claude-plugins` |                          | Claude Code plugins                           |
| `./install/zsh`            |                          | Set zsh as default shell                      |

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
stow -D nvim tmux zsh claude kanata scripts
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

- Open Neovim and run `:PackUpdate` (see `:PackStatus`)
- Check `:checkhealth` for issues

**Symlinks not working:**

- Ensure original configs are backed up/removed before running stow
- Check `ls -la ~` to verify symlinks point to `~/dotfiles/`
