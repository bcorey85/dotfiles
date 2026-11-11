-- dredge-roles-warm — theme-mode family "dredge-roles-warm" (dark): dredge-roles on a
-- warm graphite ground. Its light mode is dredge-roles unchanged. Each step sits OKLCH L 0.05 above dredge's, at C 0.006, h 90.

vim.g.dredge_overrides = {
  dark = {
    bg = "#24231f",
    bg_dark = "#1c1b18",
    bg_line = "#31302d",
    bg_cursor = "#2a2926",
    bg_sel = "#3d3c38",
    bg_visual = "#43423e",
    border = "#494845",
    nontext = "#4e4c49",
    -- The greys keep dredge's lightness, at C 0.01, h 90.
    linenr = "#929089",
    muted = "#b7b5ae",
    comment = "#c5c2bc",
    punct = "#98958f",
    fg = "#c3c1ba",
    fg_bright = "#f4f1ea",
    kw = "#a09e97",
    term = {
      "#1c1b18", "#f76c66", "#5cbd6e", "#ccb03f", "#36aff6", "#fc61a5", "#46b8ae", "#e1ded7",
      "#929089", "#ffc4bd", "#c5fbcf", "#ffe9ad", "#bdeaff", "#ff95c4", "#b0efe8", "#f4f1ea",
    },
  },
}
vim.g.dredge_role_overrides = { dark = { read = "#c3c1ba", kw = "#a09e97" } }
vim.cmd.runtime("colors/dredge-roles.lua")
vim.g.dredge_overrides = nil
vim.g.dredge_role_overrides = nil
vim.g.colors_name = "dredge-roles-warm"
