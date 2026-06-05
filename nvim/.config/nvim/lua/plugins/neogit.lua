local in_popup = vim.env.NEOGIT_POPUP ~= nil

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
        if vim.env.TMUX then
          local zoomed = vim.fn.system("tmux display-message -p '#{window_zoomed_flag}'"):gsub("%s+", "")
          if zoomed == "1" then
            vim.fn.system("tmux resize-pane -Z")
          end
        end
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
        if vim.env.TMUX then
          local zoomed = vim.fn.system("tmux display-message -p '#{window_zoomed_flag}'"):gsub("%s+", "")
          if zoomed ~= "1" then
            vim.fn.system("tmux resize-pane -Z")
          end
        end
        require("neogit").open()
      end,
      desc = "Neogit (zoomed)",
    },
  },
}
