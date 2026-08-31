-- bamboo (ribru17/bamboo.nvim) — theme-mode family. Warm green-brown "vulgaris"
-- dark #252623 / warm cream light #fafae0. Loads eagerly (lazy = false,
-- priority = 1000) so it's on the rtp before config.lazy.lua's
-- theme-sync.start(). The `bamboo` colorscheme picks its style from
-- vim.o.background (light => the light palette, otherwise vulgaris) and always
-- sets colors_name to "bamboo", so theme-sync pins both.
return {
  "ribru17/bamboo.nvim",
  name = "bamboo",
  lazy = false,
  priority = 1000,
}
