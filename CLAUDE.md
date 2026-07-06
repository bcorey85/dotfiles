# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

Personal dotfiles managed with **GNU Stow** across WSL, Ubuntu, macOS, and Arch Linux. Each top-level directory is a stow package that mirrors the home directory structure (e.g., `nvim/.config/nvim/` symlinks to `~/.config/nvim/`).

## Setup & Install

```bash
./setup wsl    # or: ./setup ubuntu | ./setup mac | ./setup arch
```

Individual scripts in `install/` can be run standalone:

- `install/deps <platform>` - system packages (apt/brew/pacman)
- `install/fonts <platform>` - JetBrainsMono Nerd Font
- `install/stow` - create all symlinks
- `install/doom` - clone doomemacs to `~/.config/emacs` and run `doom sync` (skips if emacs absent; the `doom` package supplies the config)
- `install/wifi-be200` - Intel BE200 Wi-Fi 7 stability fix (writes `/etc/modprobe.d/iwlwifi.conf` to disable 802.11be; auto-skips if no BE200 detected)
- `install/zsh-plugins` - clone fzf-tab, zsh-autosuggestions, zsh-syntax-highlighting to `~/.zsh/plugins/`
- `install/tmux-plugins` - clone tmux-resurrect + tmux-continuum to `~/.tmux/plugins/` (crash-proof sessions; loaded from `.tmux.conf`, no TPM)
- `install/starship` - Starship prompt
- `install/claude-plugins` - Claude Code plugins (skips if Claude not installed)
- `install/zsh` - set zsh as default shell

To add/remove a stow package, edit the `stow -R` line in `install/stow`.

## Stow Packages

| Package               | Target                                                        | Key files                                                                                                                                                                                                                                                                   |
| --------------------- | ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `nvim`                | `~/.config/nvim/`                                             | lazy.nvim config (bootstrap in `lua/config/lazy.lua`), one spec file per plugin in `lua/plugins/` (mini.* modules consolidated in `mini.lua`)                                                                                                                               |
| `tmux`                | `~/.tmux.conf`                                                | Prefix=`Ctrl+Space`, vim-style panes                                                                                                                                                                                                                                        |
| `zsh`                 | `~/.zshrc`                                                    | Plugins, aliases, pyenv/nvm/starship init                                                                                                                                                                                                                                   |
| `claude`              | `~/.claude/`                                                  | Agents, commands, settings, hooks                                                                                                                                                                                                                                           |
| `opencode`            | `~/.config/opencode/`                                         | Global config (`opencode.jsonc`), `AGENTS.md` global rules, `agents/` ported from claude. Auto-loads `~/.claude/skills/`                                                                                                                                                    |
| `aerospace`           | `~/.config/aerospace/`                                        | macOS tiling WM. Workspaces 1-9 pinned to external monitor, built-in screen dedicated to Teams (mac only)                                                                                                                                                                   |
| `starship`            | `~/.config/starship.toml`                                     | github dark dimmed prompt                                                                                                                                                                                                                                                   |
| `kanata`              | `~/kanata-config.kbd`, `~/kanata-setup`, `~/kanata-setup-mac` | Keyboard remapping. Linux: systemd service (`kanata-setup`). macOS: launchd + Karabiner driver (`kanata-setup-mac`)                                                                                                                                                         |
| `scripts`             | `~/.local/bin/`                                               | tmux-sessionizer, dev utilities                                                                                                                                                                                                                                             |
| `git`                 | `~/.gitconfig`                                                | Delta pager, side-by-side diffs. Per-machine identity in `~/.gitconfig.local`                                                                                                                                                                                               |
| `doom`                | `~/.config/doom/`                                             | Doom Emacs config (`config.el`, `init.el`, `packages.el`). Framework itself is not stowed — `install/doom` bootstraps it to `~/.config/emacs`. tmux-style sessionizer + dev layouts + harpoon live in `config.el`                                                           |
| `applications` (Arch) | `~/.local/share/applications/`                                | XDG desktop-entry overrides. `emacsclient.desktop` shadows Arch's entry: starts the systemd `emacs.service` daemon first, then connects with a non-self-daemonizing `emacsclient` (upstream's `--alternate-editor=` races the service and spawns a second, fighting daemon) |

## CRITICAL: Cross-Platform Compatibility

**Everything in this repo MUST work on all four platforms: WSL, Ubuntu, macOS, and Arch Linux.** Before installing any tool, adding any dependency, or making any change:

1. **Only use `apt` (WSL/Ubuntu), `brew` (macOS), and `pacman` (Arch)** for package installs — never `cargo`, `pip install --global`, `snap`, or other package managers
2. **Add new dependencies to `install/deps`** in ALL platform cases (`wsl|ubuntu`, `mac`, and `arch`)
3. **Never hardcode platform-specific paths** — use `$HOME`, `~`, or detect the platform
4. **Per-machine config** (user identity, credentials, machine-specific paths) belongs in local files (e.g., `~/.gitconfig.local`), NOT in stow-managed files

## Key Conventions

- **Theme**: single family (github-nvim-theme, projekt0n/github-nvim-theme), one state file. **Mode** (`~/.cache/theme-mode`, toggled by `theme-mode` / tmux `prefix T` / nvim `<leader>ut` / Emacs `SPC t t`): dark (`github_dark_dimmed`: bg `#22272e`, fg `#adbac7`, blue `#539bf5` primary accent, cyan `#76e3ea`, green `#57ab5a`, red `#f47067`) or light (`github_light`: bg `#ffffff`, fg `#1f2328`, blue `#0969da`). tmux sources `~/.config/tmux/github-{mode}.conf`; nvim polls the state file (lua/config/theme-sync.lua); Emacs watches it and remaps modus-vivendi/modus-operandi to the github palette (no Emacs port exists); ghostty is static (`theme = GitHub Dark Dimmed`, not wired to the toggle — reload with ctrl+shift+, after editing). **Dark-only, no mode switching**: starship, waybar, rofi, dunst, hyprland, hyprlock — all github_dark_dimmed hex values. GTK/Qt apps use Adwaita-dark.
- **Font**: JetBrainsMono Nerd Font Mono, 11pt (ghostty)
- **Platform guards**: Use `command -v <tool> &>/dev/null &&` before tool-specific init (see .zshrc)
- **Install scripts**: All use the same color output pattern (`print_success`, `print_error`, `print_info`) with `set -e`
- **Stow structure**: `<package>/<home-relative-path>` (e.g., `nvim/.config/nvim/init.lua` becomes `~/.config/nvim/init.lua`)

## Working with This Repo

- **Direct-edit repo**: the global delegation mandate does not apply here — edit files directly instead of dispatching coder subagents
- Configs are live-symlinked; edits in `~/dotfiles/` take effect immediately (except tmux which needs `tmux source-file ~/.tmux.conf`)
- Neovim plugins are managed by **lazy.nvim** (bootstrap in `lua/config/lazy.lua`); specs live in `lua/plugins/` (one file per plugin; all `mini.*` modules share a single consolidated `mini.lua` spec because lazy merges same-repo specs and only keeps one `config`). Revisions are pinned in `lazy-lock.json`; use `:Lazy` (status/install/update/clean) — `:PackUpdate`/`:PackStatus`/`:PackClean` remain as compat aliases. Load triggers (`event`/`ft`/`cmd`/`keys`) are set per spec; a spec with no trigger and no `lazy = true` loads eagerly at startup. LSP is wired from the `lspconfig` spec's `config` (gated on `BufReadPre`) so `config.lsp` runs only after nvim-lspconfig is on the rtp.
- Zsh plugins are git-cloned to `~/.zsh/plugins/` (not in this repo, installed by `install/zsh-plugins`)
- Kanata setup is post-install and per-OS: Linux `sudo ~/kanata-setup` (systemd service + udev rules); macOS `sudo ~/kanata-setup-mac` (Homebrew kanata + version-pinned Karabiner driver + launchd daemons, then manual Driver Extension / Input Monitoring / Accessibility approvals + reboot)
- opencode global config is stowed at `opencode/.config/opencode/opencode.jsonc`; it auto-loads external skills from `~/.claude/skills/`, so existing stowed claude skills work as-is. opencode-specific agents/commands live under `~/.config/opencode/agent(s)/` and `command(s)/` (port from claude separately if desired)
