-- flexoki (cpplain/flexoki.nvim) — wired into theme-mode/theme-sync. Loads
-- eagerly (lazy = false, priority = 1000) so it's on the rtp before
-- config.lazy.lua's theme-sync.start(). One colorscheme "flexoki" switches via
-- vim.o.background, so theme-sync pins both the scheme name and colors_name for
-- its override guard.
--
-- NOT kepano/flexoki-neovim: that upstream's current main assigns roles from a
-- different scheme (String cyan, Keyword green, Function orange) and references
-- palette keys its own palette.lua does not define. This port is archived
-- upstream — hence read-only and pinned in lazy-lock.json — but complete, and
-- its role map is the one the herdr/starship/hunk flexoki palettes encode.
return {
  "cpplain/flexoki.nvim",
  name = "flexoki",
  lazy = false,
  priority = 1000,
}
