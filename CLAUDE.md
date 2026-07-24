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
- `install/mise` - global node LTS via mise (mise itself comes from `install/deps`; replaces `install/nvm` in `./setup` — `.zshrc` falls back to nvm on machines without mise)
- `install/gh-dash` - gh-dash PR/issue dashboard extension (skips if gh missing or unauthenticated; re-run after `gh auth login`)
- `install/workmux` - workmux (parallel claude sessions via git worktrees + tmux windows): brew tap on macOS, checksum-verified GitHub release binary to `~/.local/bin` on Linux (no apt/pacman package; re-run with `--update` to upgrade). Global config is the stowed `workmux` package; dashboard on tmux `prefix w`; window status icons come from the `workmux-status` claude plugin (installed by `install/claude-plugins`)
- `install/daily-recap` - schedule nightly `claude -p "/daily-recap"` (weekdays 18:00): compiles org captures (`~/vault/org`: journal entries + todo completions/opens) + GitHub activity into a structured daily note in the vault. macOS LaunchAgent / Linux systemd user timer; skips if claude absent. Capture side is `scripts/.local/bin/todo` + nvim-orgmode (tmux `prefix n`)
- `install/weekly-recap` - schedule `claude -p "/weekly-recap"` (Fridays 18:30, after Friday's daily compile): rolls the week's Daily notes into `~/vault/Weekly/<ISO-week>.md` (decisions, themes, shipped, current open org todos) and appends brag bullets to `~/vault/Brag/<year>.md`. Same LaunchAgent/systemd pattern as daily-recap
- `install/starship` - Starship prompt
- `install/claude-plugins` - Claude Code plugins (skips if Claude not installed)
- `install/zsh` - set zsh as default shell

To add/remove a stow package, edit the `stow -R` line in `install/stow`.

## Stow Packages

| Package               | Target                                                        | Key files                                                                                                                                                                                                                                                                   |
| --------------------- | ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `nvim`                | `~/.config/nvim/`                                             | lazy.nvim config (bootstrap in `lua/config/lazy.lua`), one spec file per plugin in `lua/plugins/` (mini.* modules consolidated in `mini.lua`)                                                                                                                               |
| `tmux`                | `~/.tmux.conf`                                                | Prefix=`Ctrl+Space`, vim-style panes                                                                                                                                                                                                                                        |
| `zsh`                 | `~/.zshrc`                                                    | Plugins, aliases, mise/pyenv/starship init (nvm fallback when mise absent)                                                                                                                                                                                                  |
| `claude`              | `~/.claude/`                                                  | Agents, commands, settings, hooks                                                                                                                                                                                                                                           |
| `opencode`            | `~/.config/opencode/`                                         | Global config (`opencode.jsonc`), `AGENTS.md` global rules, `agents/` ported from claude. Auto-loads `~/.claude/skills/`                                                                                                                                                    |
| `aerospace`           | `~/.config/aerospace/`                                        | macOS tiling WM. Workspaces 1-9 pinned to external monitor, built-in screen dedicated to Teams (mac only)                                                                                                                                                                   |
| `starship`            | `~/.config/starship.toml`                                     | github dark dimmed prompt                                                                                                                                                                                                                                                   |
| `kanata`              | `~/kanata-config.kbd`, `~/kanata-setup`, `~/kanata-setup-mac` | Keyboard remapping. Linux: systemd service (`kanata-setup`). macOS: launchd + Karabiner driver (`kanata-setup-mac`)                                                                                                                                                         |
| `scripts`             | `~/.local/bin/`                                               | tmux-sessionizer, dev utilities                                                                                                                                                                                                                                             |
| `git`                 | `~/.gitconfig`                                                | Delta pager, side-by-side diffs. Per-machine identity in `~/.gitconfig.local`                                                                                                                                                                                               |
| `workmux`             | `~/.config/workmux/`                                          | workmux global config: worktrees under `~/.workmux/{project}` (keeps sessionizer scan dirs clean), single claude agent pane per worktree window. Binary via `install/workmux`; dashboard on tmux `prefix w`                                                                 |
| `doom`                | `~/.config/doom/`                                             | Doom Emacs config (`config.el`, `init.el`, `packages.el`). Framework itself is not stowed — `install/doom` bootstraps it to `~/.config/emacs`. tmux-style sessionizer + dev layouts + harpoon live in `config.el`                                                           |
| `applications` (Arch) | `~/.local/share/applications/`                                | XDG desktop-entry overrides. `emacsclient.desktop` shadows Arch's entry: starts the systemd `emacs.service` daemon first, then connects with a non-self-daemonizing `emacsclient` (upstream's `--alternate-editor=` races the service and spawns a second, fighting daemon) |

## CRITICAL: Cross-Platform Compatibility

**Everything in this repo MUST work on all four platforms: WSL, Ubuntu, macOS, and Arch Linux.** Before installing any tool, adding any dependency, or making any change:

1. **Only use `apt` (WSL/Ubuntu), `brew` (macOS), and `pacman` (Arch)** for package installs — never `cargo`, `pip install --global`, `snap`, or other package managers
2. **Add new dependencies to `install/deps`** in ALL platform cases (`wsl|ubuntu`, `mac`, and `arch`)
3. **Never hardcode platform-specific paths** — use `$HOME`, `~`, or detect the platform
4. **Per-machine config** (user identity, credentials, machine-specific paths) belongs in local files (e.g., `~/.gitconfig.local`), NOT in stow-managed files

## Key Conventions

- **Theme**: two-axis switcher, owned by the `theme-mode` script (scripts package). **Family** (`~/.cache/theme-family`: `nightfox` default; `theme-mode list` for the full set; switch with `theme-mode use <family> [mode]`) × **mode** (`~/.cache/theme-mode` dark/light, toggled by `theme-mode` / tmux `prefix T` / nvim `<leader>ut` / Emacs `SPC t t`). Consumers: tmux sources `~/.config/tmux/<family>-<mode>.conf`; nvim polls both state files (lua/config/theme-sync.lua — its FAMILIES table maps schemes and owns all theme-reactive overrides: markview headings, gitsigns word-diff, per-family fixups like carbonfox's comment-contrast lift); ghostty gets `theme-switch.conf` (machine-local include written by the script; reload ctrl+shift+, — custom palettes live in `ghostty/.config/ghostty/themes/`); Emacs is mode-only (remaps modus-vivendi/modus-operandi to the github palette); starship is mode-only too (theme-mode regenerates `~/.cache/starship.toml` from the stowed template with the active `dark`/`light` palette, and `.zshrc` points STARSHIP_CONFIG at the cache — starship has no include but re-reads config each prompt). Adding a family = 4 touchpoints, listed in the `theme-mode` header. **Dark-only, no mode switching**: waybar, rofi, dunst, hyprland, hyprlock — all github_dark_dimmed hex values. GTK/Qt apps use Adwaita-dark.
- **Font**: JetBrainsMono Nerd Font Mono, 11pt (ghostty)
- **Platform guards**: Use `command -v <tool> &>/dev/null &&` before tool-specific init (see .zshrc)
- **Install scripts**: All use the same color output pattern (`print_success`, `print_error`, `print_info`) with `set -e`
- **Stow structure**: `<package>/<home-relative-path>` (e.g., `nvim/.config/nvim/init.lua` becomes `~/.config/nvim/init.lua`)

## Working with This Repo

- **Direct-edit repo**: the global delegation mandate does not apply here — edit files directly instead of dispatching coder subagents
- **Toolkit-edit propagation sweep** (run before claiming done on any change to an agent/skill under `claude/.claude/`; a done-claim without it is a guess): (1) `grep -r` the changed tag/field/section name across the repo — update every consumer (routing in `review-loop.md`, the telemetry log call, `audit/review.md`); (2) patch the ported copy in `opencode/.config/opencode/agents/` or state that you're knowingly skipping it (adaptations preserved there: CLAUDE.md→AGENTS.md, no Persistent Memory, opencode frontmatter); (3) check inheriting variants (`-deep` agents inherit by reference — usually no edit; coders preload `coder-core`, which opencode auto-loads).
- Configs are live-symlinked; edits in `~/dotfiles/` take effect immediately (except tmux which needs `tmux source-file ~/.tmux.conf`)
- Neovim plugins are managed by **lazy.nvim** (bootstrap in `lua/config/lazy.lua`); specs live in `lua/plugins/` (one file per plugin; all `mini.*` modules share a single consolidated `mini.lua` spec because lazy merges same-repo specs and only keeps one `config`). Revisions are pinned in `lazy-lock.json`; use `:Lazy` (status/install/update/clean) — `:PackUpdate`/`:PackStatus`/`:PackClean` remain as compat aliases. Load triggers (`event`/`ft`/`cmd`/`keys`) are set per spec; a spec with no trigger and no `lazy = true` loads eagerly at startup. LSP is wired from the `lspconfig` spec's `config` (gated on `BufReadPre`) so `config.lsp` runs only after nvim-lspconfig is on the rtp.
- Zsh plugins are git-cloned to `~/.zsh/plugins/` (not in this repo, installed by `install/zsh-plugins`)
- Kanata setup is post-install and per-OS: Linux `sudo ~/kanata-setup` (systemd service + udev rules); macOS `sudo ~/kanata-setup-mac` (Homebrew kanata + version-pinned Karabiner driver + launchd daemons, then manual Driver Extension / Input Monitoring / Accessibility approvals + reboot)
- opencode global config is stowed at `opencode/.config/opencode/opencode.jsonc`; it auto-loads external skills from `~/.claude/skills/`, so existing stowed claude skills work as-is. opencode-specific agents/commands live under `~/.config/opencode/agent(s)/` and `command(s)/` (port from claude separately if desired)
