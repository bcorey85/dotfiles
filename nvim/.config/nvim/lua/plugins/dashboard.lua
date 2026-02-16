return {
  "nvimdev/dashboard-nvim",
  event = "VimEnter",
  dependencies = { "nvim-tree/nvim-web-devicons" },
  keys = {
    { "<leader>D", "<cmd>Dashboard<cr>", desc = "Dashboard" },
  },
  config = function()
    require("dashboard").setup({
      theme = "hyper",
      config = {
        week_header = {
          enable = true,
        },
        shortcut = {
          { desc = "󰊳 Update", group = "DiagnosticInfo", action = "Lazy update", key = "u" },
          {
            icon = " ",
            icon_hl = "DiagnosticOk",
            desc = "Files",
            group = "DiagnosticOk",
            action = "lua Snacks.picker.files()",
            key = "f",
          },
          {
            icon = " ",
            desc = "Grep",
            group = "DiagnosticHint",
            action = "lua Snacks.picker.grep()",
            key = "g",
          },
          {
            icon = " ",
            desc = "Recent",
            group = "DiagnosticWarn",
            action = "lua Snacks.picker.recent()",
            key = "r",
          },
        },
        packages = { enable = true },
        project = {
          enable = true,
          limit = 5,
          icon = " ",
          label = " Recent Projects",
          action = function(path)
            Snacks.picker.files({ cwd = path })
          end,
        },
        mru = {
          enable = true,
          limit = 8,
          icon = " ",
          label = " Recent Files",
          cwd_only = false,
        },
        footer = function()
          local branch = vim.fn.system("git branch --show-current 2>/dev/null"):gsub("\n", "")
          local cwd = vim.fn.fnamemodify(vim.fn.getcwd(), ":~")
          local lines = {}
          if branch ~= "" then
            table.insert(lines, " " .. branch .. "  |  " .. " " .. cwd)
          else
            table.insert(lines, " " .. cwd)
          end
          return lines
        end,
      },
    })
  end,
}
