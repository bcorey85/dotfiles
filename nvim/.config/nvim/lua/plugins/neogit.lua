local in_popup = vim.env.NEOGIT_POPUP ~= nil
local tmux = require("util.tmux")

return {
  "NeogitOrg/neogit",
  cmd = "Neogit",
  dependencies = {
    "nvim-lua/plenary.nvim",
    "dlyongemallo/diffview.nvim",
  },
  opts = {
    integrations = { diffview = true },
    kind = "tab",
  },
  config = function(_, opts)
    require("neogit").setup(opts)

    local augroup = vim.api.nvim_create_augroup("NeogitStatusClose", { clear = true })

    vim.api.nvim_create_autocmd("BufWinLeave", {
      group = augroup,
      pattern = "NeogitStatus",
      callback = function()
        if in_popup then
          vim.cmd("qa")
          return
        end
        tmux.unzoom()
      end,
    })
  end,
  keys = {
    {
      "<leader>gg",
      function()
        if in_popup then
          require("neogit").open()
          return
        end
        tmux.zoom()
        require("neogit").open()
      end,
      desc = "Neogit (zoomed)",
    },
    {
      "<leader>gl",
      function()
        require("neogit").open({ "log" })
      end,
      desc = "Git log (neogit)",
    },
  },
}
