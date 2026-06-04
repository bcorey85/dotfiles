-- Winbar breadcrumbs: VSCode-style "dir › file › Class › method" location indicator.
-- Replaces treesitter-context as the answer to "where am I in this file?" —
-- same information, but rendered in the winbar instead of stealing buffer rows.
--
-- barbecue wraps nvim-navic (which queries LSP documentSymbol) and renders
-- the result as a per-window winbar. attach_navic = true (default) makes
-- barbecue auto-attach navic to every qualifying LSP client, so lsp.lua
-- does NOT need to be touched.
--
-- vim.g.navic_silence = true suppresses the "multiple clients" warning that
-- fires when more than one LSP attaches to a buffer (e.g. vtsls + eslint).
--
-- theme = "catppuccin-mocha" delegates all highlight resolution to catppuccin
-- rather than barbecue's "auto" theme-detection, keeping colors consistent
-- with the rest of the config.
--
-- show_dirname / show_basename are left at their defaults (true) — tune them
-- here if the winbar feels too wide on smaller splits.

vim.g.navic_silence = true

return {
  "utilyre/barbecue.nvim",
  name = "barbecue",
  version = "*",
  event = { "BufReadPost", "BufNewFile" },
  dependencies = {
    "SmiteshP/nvim-navic",
    "nvim-tree/nvim-web-devicons",
  },
  opts = {
    attach_navic = true,
    theme = "catppuccin-mocha",
  },
}
