# Neovim

My personal, hand-rolled Neovim configuration.

- **Plugin manager:** lazy.nvim — bootstrap in `lua/config/lazy.lua`; use `:Lazy` (`:PackUpdate` / `:PackStatus` / `:PackClean` kept as compat aliases). Per-spec load triggers (`event`/`ft`/`cmd`/`keys`) in `lua/plugins/`
- **Layout:** `lua/config/` for core settings (options, keymaps, autocmds, LSP); `lua/plugins/` with one spec file per plugin
- **LSP:** native `vim.lsp.config` / `vim.lsp.enable`, servers installed via Mason
- **Theme:** two-axis family × light/dark switcher (default nightfox), synced across nvim/tmux/ghostty by the `theme-mode` script; families and per-family overrides live in `lua/config/theme-sync.lua`

Stow-managed as part of my dotfiles; symlinked to `~/.config/nvim/`.
