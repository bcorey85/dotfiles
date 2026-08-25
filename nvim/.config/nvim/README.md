# Neovim

My personal, hand-rolled Neovim configuration.

- **Plugin manager:** lazy.nvim — bootstrap in `lua/config/lazy.lua`; use `:Lazy` (`:PackUpdate` / `:PackStatus` / `:PackClean` kept as compat aliases). Per-spec load triggers (`event`/`ft`/`cmd`/`keys`) in `lua/plugins/`
- **Layout:** `lua/config/` for core settings (options, keymaps, autocmds, LSP); `lua/plugins/` with one spec file per plugin
- **LSP:** native `vim.lsp.config` / `vim.lsp.enable`, servers installed via Mason
- **Theme:** four families — flexoki (kepano/flexoki-neovim, native; dark / light), token (ThorstenRhau/token, warm cream; dark / light), flume (mitander/flume.nvim; dark = mira, light = mesa; the default), and kanso (webhooked/kanso.nvim, kanagawa lineage; dark = zen, light = pearl); pick with `theme-use <family> [mode]`; light/dark synced across nvim/ghostty by the `theme-mode` script; the family registry and its overrides live in `lua/config/theme-sync.lua`

Stow-managed as part of my dotfiles; symlinked to `~/.config/nvim/`.
