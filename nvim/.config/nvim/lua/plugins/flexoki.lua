-- flexoki (cpplain/flexoki.nvim) — second theme family, wired into
-- theme-mode/theme-sync. Loads eagerly (lazy = false, priority = 1000) so it's
-- on the rtp before config.lazy.lua's theme-sync.start(). One colorscheme entry
-- ("flexoki", colors_name = "flexoki") that reads vim.o.background at load, so
-- theme-sync's apply() sets background before :colorscheme (schemes.dark ==
-- schemes.light == "flexoki"). Chosen over kepano/flexoki-neovim for a calmer
-- mapping: identifiers, members, operators and params stay neutral tx instead
-- of each taking an accent, so code reads less rainbow.
return {
  "cpplain/flexoki.nvim",
  name = "flexoki",
  lazy = false,
  priority = 1000,
}
