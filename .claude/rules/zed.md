---
paths:
  - "zed/**"
---

# zed

`settings.json` + `keymap.json`, a GUI editor kept deliberately close to the nvim/herdr layout: vim mode on, space leader, FiraCode Nerd Font Mono Retina 13, the `options.lua` core (relative numbers, scrolloff 4, tab 4, format-on-save, soft wrap). Zed is NOT on the `theme-mode` axis — it ships no `edge` port and never reads `~/.cache/theme-*`, so `theme.mode` is set by hand.

**No binding may be a prefix of another** — Zed fires the shorter one immediately, so Zed's default `space f` is unbound to `null` to make room for `space f s/n/p`, and the file finder moved to `space space`. Panel keys bind the PANEL (`outline_panel::Toggle`), never the dock — `workspace::ToggleLeftDock` toggles whatever is docked left, and `ToggleFocus` only focuses, never closes. `space e` is nvim's fyler sidebar key, so it is `pane::RevealInProjectPanel` (cursor on the current file), NOT a panel toggle; inside the panel the same key closes it, mirroring fyler's `<leader>e` toggle. Tab order stands in for nvim's buffer_manager list: `space 1..4` / `alt+1..4` jump by tab position, `space a` pins a tab to the front, `space tab` is the switcher. Agent threads own `space t`, so nvim's `<leader>tt` terminal has no leader equivalent here. `ctrl-hjkl` moves between Zed panes only — it does not cross into herdr.

The stowed files are real config, not templates.
