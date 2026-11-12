-- rose-pine (rose-pine/neovim) — theme-mode family. Main #191724 dark / dawn
-- #faf4ed light. Loads eagerly (lazy = false, priority = 1000) so it's on the
-- rtp before config.lazy.lua's theme-sync.start().
--
-- "rose-pine-main" and "rose-pine-dawn" both set colors_name "rose-pine", so
-- theme-sync pins it.
return {
  "rose-pine/neovim",
  name = "rose-pine",
  lazy = false,
  priority = 1000,
}
