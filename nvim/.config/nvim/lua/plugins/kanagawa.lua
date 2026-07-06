-- kanagawa — stock except two deliberate changes to the dragon variant:
--
-- 1. bg lifted #181616 → #1e1c1c (bg L 0.008 → 0.012). Stock depth
--    dark-adapts the eye (pupil dilation → astigmatism halation; glaucoma
--    contrast sensitivity drops at low luminance); the lift lands near the
--    proven-comfortable band while keeping dragon's neutral-black hue. Same
--    value is applied in ghostty and tmux dark.conf so every surface matches.
-- 2. floats neutralized: stock is oldWhite #c8c093 (yellow cast) on
--    dragonBlack0 #0d0c0c (near-black "aged paper" look); pickers/popups now
--    use the editor ink on the stock editor bg — one step darker than the
--    lifted canvas, so floats still read as a distinct surface.
--
-- dark = kanagawa-dragon, light = kanagawa-lotus, selected by
-- lua/config/theme-sync.lua off the shared ~/.cache/theme-mode state file.
return {
  "rebelot/kanagawa.nvim",
  lazy = false,
  priority = 1000,
  config = function()
    require("kanagawa").setup({
      colors = {
        theme = {
          dragon = {
            ui = {
              bg = "#1e1c1c",
              float = { fg = "#c5c9c5", bg = "#181616" },
            },
          },
        },
      },
    })
  end,
}
