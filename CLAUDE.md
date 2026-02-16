# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

Personal dotfiles managed with **GNU Stow** across WSL, Ubuntu, and macOS. Each top-level directory is a stow package that mirrors the home directory structure (e.g., `nvim/.config/nvim/` symlinks to `~/.config/nvim/`).

## Setup & Install

```bash
./setup wsl    # or: ./setup ubuntu | ./setup mac
```

Individual scripts in `install/` can be run standalone:
- `install/deps <platform>` - system packages (apt/brew)
- `install/fonts <platform>` - CommitMono Nerd Font
- `install/stow` - create all symlinks
- `install/zsh-plugins` - clone fzf-tab, zsh-autosuggestions, zsh-syntax-highlighting to `~/.zsh/plugins/`
- `install/tmux-plugins` - TPM and tmux plugins
- `install/starship` - Starship prompt
- `install/claude-plugins` - Claude Code plugins (skips if Claude not installed)
- `install/zsh` - set zsh as default shell

To add/remove a stow package, edit the `stow -R` line in `install/stow`.

## Stow Packages

| Package | Target | Key files |
|---------|--------|-----------|
| `nvim` | `~/.config/nvim/` | LazyVim config, `lua/plugins/*.lua` (22 plugin configs) |
| `tmux` | `~/.tmux.conf` | Prefix=`Ctrl+Space`, vim-style panes, TPM |
| `zsh` | `~/.zshrc` | Plugins, aliases, pyenv/nvm/starship init |
| `claude` | `~/.claude/` | Agents, commands, settings, hooks |
| `kitty` | `~/.config/kitty/` | Gruvbox Material Dark Medium theme |
| `alacritty` | `~/.config/alacritty/` | Gruvbox Material Dark Hard theme, same font as kitty |
| `starship` | `~/.config/starship.toml` | Gruvbox Material prompt |
| `yazi` | `~/.config/yazi/` | File manager config |
| `kanata` | `~/kanata-config.kbd`, `~/kanata-setup` | Keyboard remapping with systemd service |
| `scripts` | `~/.local/bin/` | tmux-sessionizer, dev utilities |
| `lazygit` | `~/.config/lazygit/` | Narrow side panel, expand on focus |
| `git` | `~/.gitconfig` | Delta pager, side-by-side diffs. Per-machine identity in `~/.gitconfig.local` |

## CRITICAL: Cross-Platform Compatibility

**Everything in this repo MUST work on all three platforms: WSL, Ubuntu, and macOS.** Before installing any tool, adding any dependency, or making any change:

1. **Only use `apt` (WSL/Ubuntu) and `brew` (macOS)** for package installs — never `cargo`, `pip install --global`, `snap`, or other package managers
2. **Add new dependencies to `install/deps`** in BOTH the `wsl|ubuntu` and `mac` cases
3. **Never hardcode platform-specific paths** — use `$HOME`, `~`, or detect the platform
4. **Per-machine config** (user identity, credentials, machine-specific paths) belongs in local files (e.g., `~/.gitconfig.local`), NOT in stow-managed files

## Key Conventions

- **Theme**: Sonokai Maia everywhere (kitty, alacritty, starship, neovim, tmux)
- **Font**: CommitMono Nerd Font Mono, 12pt
- **Platform guards**: Use `command -v <tool> &>/dev/null &&` before tool-specific init (see .zshrc)
- **Install scripts**: All use the same color output pattern (`print_success`, `print_error`, `print_info`) with `set -e`
- **Stow structure**: `<package>/<home-relative-path>` (e.g., `nvim/.config/nvim/init.lua` becomes `~/.config/nvim/init.lua`)

## Working with This Repo

- Configs are live-symlinked; edits in `~/dotfiles/` take effect immediately (except tmux which needs `tmux source-file ~/.tmux.conf`)
- Neovim plugins are managed by Lazy.nvim; `lazy-lock.json` is gitignored
- Zsh plugins are git-cloned to `~/.zsh/plugins/` (not in this repo, installed by `install/zsh-plugins`)
- Tmux plugins are managed by TPM at `~/.tmux/plugins/` (installed by `install/tmux-plugins`)
- Kanata setup requires `sudo ~/kanata-setup` post-install for systemd service and udev rules
