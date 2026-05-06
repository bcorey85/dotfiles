local exclude = {
  "node_modules",
  "dist",
  "build",
  "__pycache__",
  ".venv",
  "*.pyc",
  ".mypy_cache",
  ".ruff_cache",
  "staticfiles",
  "media",
  "*.sqlite3",
  ".git",
  ".nuxt",
}

return {
  "folke/snacks.nvim",
  opts = {
    picker = {
      sources = {
        explorer = {
          hidden = true,
          ignored = true,
          exclude = { ".git" },
          watcher = true,
        },
        files = {
          hidden = true,
          ignored = false,
          follow = true,
          exclude = exclude,
        },
        grep = {
          hidden = true,
          ignored = false,
          follow = true,
          exclude = exclude,
        },
      },
    },
  },
  keys = {
    {
      "<leader>fI",
      function()
        Snacks.picker.files({ hidden = true, ignored = true })
      end,
      desc = "Find files (including ignored)",
    },
    {
      "<leader>gs",
      function()
        Snacks.picker.git_status({
          layout = "sidebar",
        })
      end,
      desc = "Git Status (sidebar)",
    },
    {
      "<leader>gg",
      function()
        local in_tmux = vim.env.TMUX ~= nil
        if in_tmux then
          local zoomed = vim.fn.system("tmux display-message -p '#{window_zoomed_flag}'"):gsub("%s+", "")
          if zoomed ~= "1" then
            vim.fn.system("tmux resize-pane -Z")
          end
        end
        Snacks.lazygit({
          win = {
            width = 0.99,
            height = 0.99,
            on_close = function()
              if in_tmux then
                local zoomed = vim.fn.system("tmux display-message -p '#{window_zoomed_flag}'"):gsub("%s+", "")
                if zoomed == "1" then
                  vim.fn.system("tmux resize-pane -Z")
                end
              end
            end,
          },
        })
      end,
      desc = "Lazygit (zoomed)",
    },
  },
}
