-- material (marko-cerovac/material.nvim) — theme-mode family. OneDark-genre
-- vivid on neutral: "darker" #212121 dark / "lighter" #FAFAFA light. Loads
-- eagerly (lazy = false, priority = 1000) so it's on the rtp before
-- config.lazy.lua's theme-sync.start().
--
-- Ships one colorscheme PER style ("material-darker" / "material-lighter"),
-- but both register colors_name "material", so theme-sync names the schemes
-- separately AND pins colors_name (kanagawa pattern). The style files set
-- vim.g.material_style themselves — no setup() call needed.
return {
  "marko-cerovac/material.nvim",
  name = "material",
  lazy = false,
  priority = 1000,
}
