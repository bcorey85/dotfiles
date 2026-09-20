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
- `install/fonts <platform>` - FiraCode Nerd Font
- `install/stow` - create all symlinks
- `install/wifi-be200` - Intel BE200 Wi-Fi 7 stability fix (writes `/etc/modprobe.d/iwlwifi.conf` to disable 802.11be; auto-skips if no BE200 detected)
- `install/zsh-plugins` - clone fzf-tab, zsh-autosuggestions, zsh-syntax-highlighting to `~/.zsh/plugins/`
- `install/mise` - global node LTS via mise (mise itself comes from `install/deps`; replaces `install/nvm` in `./setup` — `.zshrc` falls back to nvm on machines without mise)
- `install/hunk` - hunk diff viewer (`npm i -g hunkdiff` through mise's node, then `mise reshim`; skips if mise or mise-managed node is missing). npm-global because hunk ships on npm only — no apt/brew/pacman package
- `install/gh-dash` - gh-dash PR/issue dashboard extension (skips if gh missing or unauthenticated; re-run after `gh auth login`)
- `install/herdr` - herdr (agent-aware terminal multiplexer; **the multiplexer** — the previous multiplexer package was removed 2026-08 once the migration finished): checksum-verified GitHub release binary to `~/.local/bin` (no apt/pacman/brew package; upstream ships no checksum asset, so the script pins VERSION + SHA256 — bump both to upgrade, `--update` forces reinstall). Config is the stowed `herdr` package. Workflow plugins listed in the script's `PLUGINS` var are installed idempotently on every run, including the already-installed early-exit path — currently `lmilojevicc/herdr-splits.nvim` for C/M-hjkl nav (nvim side is `lua/plugins/herdr-splits.lua`, gated on `HERDR_ENV`, installed by lazy)
- `install/daily-recap` - schedule nightly `claude -p "/daily-recap"` (weekdays 18:00): compiles org captures (`~/vault/org`: journal entries + todo completions/opens) + GitHub activity into a structured daily note in the vault. macOS LaunchAgent / Linux systemd user timer; skips if claude absent. Capture side is `scripts/.local/bin/todo` + nvim-orgmode (herdr `prefix n`)
- `install/weekly-recap` - schedule `claude -p "/weekly-recap"` (Fridays 18:30, after Friday's daily compile): rolls the week's Daily notes into `~/vault/Weekly/<ISO-week>.md` (decisions, themes, shipped, current open org todos) and copies that week's `~/vault/org/achievements.org` entries verbatim into `~/vault/Achievements/<year>.md`. **Achievements are never inferred** — `scripts/.local/bin/achievement` (herdr `prefix n A`) is the only source, because nothing else in the pipeline records _who_ did the work. Same LaunchAgent/systemd pattern as daily-recap
- `install/starship` - Starship prompt
- `install/claude-plugins` - Claude Code plugins (skips if Claude not installed)
- `install/zsh` - set zsh as default shell

To add/remove a stow package, edit the `stow -R` line in `install/stow`.

## Stow Packages

- `nvim` → `~/.config/nvim/` — lazy.nvim config (bootstrap in `lua/config/lazy.lua`), one spec file per plugin in `lua/plugins/` (mini.* modules consolidated in `mini.lua`)
- `zsh` → `~/.zshrc` — Plugins, aliases, mise/pyenv/starship init (nvm fallback when mise absent)
- `claude` → `~/.claude/` — Agents, commands, settings, hooks
- `opencode` → `~/.config/opencode/` — Global config (`opencode.jsonc`), `AGENTS.md` global rules, `agents/` ported from claude. Auto-loads `~/.claude/skills/`
- `omp` → `~/.omp/agent/hooks/` — Oh My Pi harness. `claude-security-bridge.ts` delegates tool-call gating to the claude package's hook scripts (single source of truth — do NOT re-port the gates). omp ignores `~/.pi` and `~/.claude/agents`
- `aerospace` → `~/.config/aerospace/` — macOS tiling WM. Workspaces 1-9 pinned to external monitor, built-in screen dedicated to Teams (mac only)
- `starship` → `~/.config/starship.toml.template` — github prompt template; theme-mode generates the real `~/.config/starship.toml` (machine-local) with the active dark/light palette — see Theme below
- `kanata` → `~/kanata-config.kbd`, `~/kanata-setup`, `~/kanata-setup-mac`, `~/sturdy.0.keylayout` — Keyboard remapping. Three layouts, switched by hold-grave + number: `qwerty` (1), `transcend` (2), `sturdy` (3; angle-modded, j↔q, /↔;) — the retired semimak/gallium layers (and the old transcend) are in git at `0538ddb^`. Linux: kanata systemd service (`kanata-setup`). macOS: launchd + Karabiner driver (`kanata-setup-mac`); `sturdy.0.keylayout` is the same layout as a native macOS input source (copy to `~/Library/Keyboard Layouts/`, then log out) for use without kanata — keep it in sync with the `sturdy` deflayer by hand
- `scripts` → `~/.local/bin/` — herdr-sessionizer, dev utilities
- `git` → `~/.gitconfig` — Delta pager, side-by-side diffs. Per-machine identity in `~/.gitconfig.local`
- `quickshell` → `~/.config/quickshell/` — QML desktop shell: bar, notification daemon, OSD, launcher (apps/clipboard/power), session lock. Replaced waybar, dunst, walker, rofi, hyprlock. Details: `.claude/rules/quickshell.md`
- `herdr` → `~/.config/herdr/` — `config.toml.template` — prefix C-Space, popup fleet, harpoon on `alt+1..4` via `herdr-harpoon`). Session persistence + agent resume are built in (no resurrect/continuum analogue needed). Stowed file is the TEMPLATE: `theme-mode` regenerates the real machine-local `config.toml` from it and runs `herdr server reload-config` — edit the template, never the generated file
- `hunk` → `~/.config/hunk/` — `extensions/claude-review.ts`, viewed-marks review extension; `prefix d` popup via `scripts/.local/bin/hunk-review-popup`. Details: `.claude/rules/hunk.md`
- `zed` → `~/.config/zed/` — vim-mode GUI editor mirroring the nvim/herdr layout; off the `theme-mode` axis. Zed writes this path itself, so a fresh install makes `install/stow` name `zed` as a conflict. Details: `.claude/rules/zed.md`

**Everything in this repo MUST work on all four platforms: WSL, Ubuntu, macOS, and Arch Linux.** Before installing any tool, adding any dependency, or making any change:

1. **Only use `apt` (WSL/Ubuntu), `brew` (macOS), and `pacman` (Arch)** for package installs — never `cargo`, `pip install --global`, `snap`, or other package managers
2. **Add new dependencies to `install/deps`** in ALL platform cases (`wsl|ubuntu`, `mac`, and `arch`)
3. **Never hardcode platform-specific paths** — use `$HOME`, `~`, or detect the platform
4. **Per-machine config** (user identity, credentials, machine-specific paths) belongs in local files (e.g., `~/.gitconfig.local`), NOT in stow-managed files

## Key Conventions

- **Theme**: two axes, family × mode, driven by `scripts/.local/bin/theme-mode` — its header owns the family list and the add-a-family checklist. Palettes live in that script, `nvim/lua/config/theme-sync.lua`, `quickshell/Theme.qml`, the starship and herdr templates, and `ghostty/themes/`. Don't restate any of it here. State files: `~/.cache/theme-family` and `~/.cache/theme-mode` (`theme-mode list`, `theme-mode use <family> [mode]`, bare `theme-mode` toggles the mode; nvim `<leader>ut`). herdr and starship are TEMPLATE-generated by the script, ghostty gets a machine-local `theme-switch.conf` include (reload ctrl+shift+,), and quickshell's `Theme.qml` watches the state files itself — so a family missing there silently falls back to flexoki. hyprland, hyprlock and GTK/Qt are dark-only and off the axis by design.
- **Font**: FiraCode Nerd Font Mono, Retina, 13pt (ghostty; machine-local `~/.config/ghostty/local.conf` overrides the size — last include wins)
- **Platform guards**: Use `command -v <tool> &>/dev/null &&` before tool-specific init (see .zshrc)
- **Install scripts**: All use the same color output pattern (`print_success`, `print_error`, `print_info`) with `set -e`
- **Stow structure**: `<package>/<home-relative-path>` (e.g., `nvim/.config/nvim/init.lua` becomes `~/.config/nvim/init.lua`)

## Working with This Repo

- **Direct-edit repo**: the global delegation mandate does not apply here — edit files directly instead of dispatching coder subagents
- **No rationale in agent/skill bodies.** Every line under `claude/.claude/agents/` and `claude/.claude/skills/` is paid for on every dispatch. Write the RULE, not why it exists: no measurement results, no dispatch/finding counts, no dates, no "this was retired because", no "measured basis", no account of the incident that motivated it. Also banned: persuasion (arguing a rule's merits to its reader), restating what a capable model does unprompted, and a second phrasing of a rule already stated in the same file. If a line doesn't change what the agent does, it doesn't ship. If a rule needs defending, the defense goes in the git commit message or `~/agent-evals/`, never in the file. Existing rationale paragraphs are debt — delete them when you touch the surrounding text.
- **Toolkit-edit propagation sweep** (run before claiming done on any change to an agent/skill under `claude/.claude/`; a done-claim without it is a guess): (1) `grep -r` the changed tag/field/section name across the repo — update every consumer (routing in `review-loop.md`, the telemetry log call, `audit/review.md`); (2) patch the ported copy in `opencode/.config/opencode/agents/` or state that you're knowingly skipping it (adaptations preserved there: CLAUDE.md→AGENTS.md, opencode frontmatter); (3) check inheriting variants (`-deep` agents inherit by reference — usually no edit; coders preload `coder-core`, which opencode auto-loads).
- Configs are live-symlinked; edits in `~/dotfiles/` take effect immediately (herdr and starship are the exceptions — their stowed files are TEMPLATES, regenerated by `theme-mode`)
- Neovim plugins are managed by **lazy.nvim** (bootstrap in `lua/config/lazy.lua`); specs live in `lua/plugins/` (one file per plugin; all `mini.*` modules share a single consolidated `mini.lua` spec because lazy merges same-repo specs and only keeps one `config`). Revisions are pinned in `lazy-lock.json`; use `:Lazy` (status/install/update/clean) — `:PackUpdate`/`:PackStatus`/`:PackClean` remain as compat aliases. Load triggers (`event`/`ft`/`cmd`/`keys`) are set per spec; a spec with no trigger and no `lazy = true` loads eagerly at startup. LSP is wired from the `lspconfig` spec's `config` (gated on `BufReadPre`) so `config.lsp` runs only after nvim-lspconfig is on the rtp.
- Kanata setup is post-install and per-OS: Linux `sudo ~/kanata-setup` (systemd service + udev rules); macOS `sudo ~/kanata-setup-mac` (Homebrew kanata + version-pinned Karabiner driver + launchd daemons, then manual Driver Extension / Input Monitoring / Accessibility approvals + reboot)
- Zsh plugins are git-cloned to `~/.zsh/plugins/` (not in this repo, installed by `install/zsh-plugins`)
- opencode global config is stowed at `opencode/.config/opencode/opencode.jsonc`; it auto-loads external skills from `~/.claude/skills/`, so existing stowed claude skills work as-is. opencode-specific agents/commands live under `~/.config/opencode/agent(s)/` and `command(s)/` (port from claude separately if desired)
- omp (Oh My Pi) reads `~/.omp/agent/`, NOT `~/.pi` (the legacy pi package's extensions are inert under omp) and NOT `~/.claude/agents` or `~/.claude/settings.json` hooks. Its hook discovery loads `hooks/pre|post/*.ts` factories. The security gates are NOT ported — `omp/.omp/agent/hooks/pre/claude-security-bridge.ts` shells out to the real scripts in `~/.claude/scripts/`, so changes to those scripts' stdin/stdout contract (hook JSON in, `permissionDecision` JSON or exit-2 out) must keep the bridge compatible. Regenerating the CB hooks needs no bridge change as long as the contract holds. omp hooks load at session start — restart omp after stowing
