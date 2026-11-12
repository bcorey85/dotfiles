-- kanagawa (rebelot/kanagawa.nvim) — theme-mode family "kanagawa": kanagawa-wave dark,
-- kanagawa-lotus light. Loads eagerly (lazy = false, priority = 1000) like the families.

local HIGHLIGHT_MODULES = { "editor", "syntax", "treesitter", "lsp", "plugins" }

-- The plugin hard-codes bold and italic on many groups beyond its *Style
-- options, so this walks every group it defines and switches both off.
local function without_bold_or_italic(colors)
  local config = require("kanagawa").config
  local overrides = {}
  for _, module_name in ipairs(HIGHLIGHT_MODULES) do
    local module = require("kanagawa.highlights." .. module_name)
    local groups = module.setup(colors, config)
    for name, spec in pairs(groups) do
      if spec.bold or spec.italic then
        overrides[name] = { bold = false, italic = false }
      end
    end
  end
  return overrides
end

return {
  "rebelot/kanagawa.nvim",
  lazy = false,
  priority = 1000,
  opts = { overrides = without_bold_or_italic },
}
