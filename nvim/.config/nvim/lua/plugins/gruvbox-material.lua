-- gruvbox-material (sainnhe/gruvbox-material) — theme-mode family. medium
-- contrast, 'mix' palette. Reads vim.g globals at :colorscheme load; one name
-- for both modes (mode via vim.o.background), so theme-sync pins colors_name and
-- re-sets the globals in pre(). Wired faithful — no color overrides.
return {
  "sainnhe/gruvbox-material",
  name = "gruvbox-material",
  lazy = false,
  priority = 1000,
  init = function()
    vim.g.gruvbox_material_background = "medium"
    vim.g.gruvbox_material_foreground = "mix"
  end,
}
