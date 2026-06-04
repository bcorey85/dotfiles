# Neovim

My personal, hand-rolled Neovim configuration.

- **Plugin manager:** lazy.nvim (`lua/config/lazy.lua`)
- **Layout:** `lua/config/` for core settings (options, keymaps, autocmds, LSP); `lua/plugins/` with one spec file per plugin
- **LSP:** native `vim.lsp.config` / `vim.lsp.enable`, servers installed via Mason
- **Theme:** Catppuccin Mocha

Stow-managed as part of my dotfiles; symlinked to `~/.config/nvim/`.
