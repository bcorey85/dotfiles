-- nightfox (EdenEast): the namesake nightfox dark — a cool blue-slate night —
-- paired with dayfox light. The family ships five darks (nightfox, duskfox,
-- nordfox, terafox, carbonfox) and two lights (dayfox, dawnfox); theme-sync
-- pins the canonical pair. Each variant registers its own colors_name.
--
-- nightfox is the DEFAULT_FAMILY, so this spec doubles as the theme-sync
-- bootstrap: it loads eagerly (lazy = false, priority = 1000) and its config
-- starts the sync, which reads ~/.cache/theme-{family,mode} and applies the
-- active scheme — lazy.nvim then auto-loads any other family's colorscheme
-- plugin on demand when theme-sync :colorscheme's it. (Previously this bootstrap
-- lived in the doom-one spec, removed when that family was dropped.) Per-family
-- scheme mapping and readability fixups live in theme-sync's FAMILIES registry.
return {
  "EdenEast/nightfox.nvim",
  lazy = false,
  priority = 1000,
  config = function()
    require("config.theme-sync").start()
  end,
}
