-- catppuccin (catppuccin/nvim) — theme-mode family. Frappe #303446 dark /
-- latte #eff1f5 light. Loads eagerly (lazy = false, priority = 1000) so it's
-- on the rtp before config.lazy.lua's theme-sync.start().
return {
  "catppuccin/nvim",
  name = "catppuccin",
  lazy = false,
  priority = 1000,
  opts = {
    lsp_styles = {
      underlines = {
        errors = { "undercurl" },
        hints = { "undercurl" },
        warnings = { "undercurl" },
        information = { "undercurl" },
        ok = { "undercurl" },
      },
    },
  },
}
