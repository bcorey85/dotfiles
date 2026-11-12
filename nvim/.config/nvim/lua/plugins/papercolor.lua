-- papercolor (NLKNguyen/papercolor-theme) — theme-mode family. Material-flavoured
-- xterm-256 palette on #1c1c1c dark / #eeeeee light. Loads eagerly
-- (lazy = false, priority = 1000) so it's on the rtp before config.lazy.lua's
-- theme-sync.start().
--
-- One colorscheme "PaperColor" follows vim.o.background and sets colors_name
-- "PaperColor" in both modes, so theme-sync pins it.
return {
  "NLKNguyen/papercolor-theme",
  name = "papercolor",
  lazy = false,
  priority = 1000,
}
