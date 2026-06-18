-- Highlight registrar. Defines a set of highlight groups and re-applies them on
-- every ColorScheme change (Neovim clears user-defined highlights when the
-- colorscheme reloads). statusline.lua and winbar.lua each hand-rolled the same
-- define() + ColorScheme-autocmd pair; this collapses both into one call.
local M = {}

-- augroup: unique augroup name for the ColorScheme autocmd.
-- groups:  { [name] = { fg=, bg=, bold=, ... }, ... } as passed to nvim_set_hl.
function M.register(augroup, groups)
  local function apply()
    for name, spec in pairs(groups) do
      vim.api.nvim_set_hl(0, name, spec)
    end
  end
  apply()
  vim.api.nvim_create_autocmd("ColorScheme", {
    group = vim.api.nvim_create_augroup(augroup, { clear = true }),
    callback = apply,
  })
end

return M
