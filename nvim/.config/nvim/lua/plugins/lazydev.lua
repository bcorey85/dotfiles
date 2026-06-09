-- LuaLS enhancements for editing Neovim config (feeds completions to blink via
-- the lazydev source in blink.lua).
return {
  src = "folke/lazydev.nvim",
  setup = function()
    require("lazydev").setup({
      library = {
        -- Load luvit types when the `vim.uv` word is found
        { path = "${3rd}/luv/library", words = { "vim%.uv" } },
      },
    })
  end,
}
