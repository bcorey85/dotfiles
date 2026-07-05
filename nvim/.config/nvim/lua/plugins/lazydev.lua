-- LuaLS enhancements for editing Neovim config (feeds completions to blink via
-- the lazydev source in blink.lua).
return {
  "folke/lazydev.nvim",
  ft = "lua",
  config = function()
    require("lazydev").setup({
      library = {
        -- Load luvit types when the `vim.uv` word is found
        { path = "${3rd}/luv/library", words = { "vim%.uv" } },
      },
    })
  end,
}
