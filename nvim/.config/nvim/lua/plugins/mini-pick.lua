return {
  "echasnovski/mini.pick",
  dependencies = { "echasnovski/mini.extra" },
  keys = {
    {
      "<leader><space>",
      function()
        local pick = require("mini.pick")
        local root = require("util.root").get()
        local blacklist = {
          ".git",
          "node_modules",
          ".venv",
          "__pycache__",
          "dist",
          "build",
          ".mypy_cache",
          ".ruff_cache",
          "staticfiles",
          "media",
          ".nuxt",
          "*.pyc",
          "*.sqlite3",
        }
        local cmd = { "fd", "--type", "f", "--color=never", "--hidden", "--no-ignore" }
        for _, entry in ipairs(blacklist) do
          table.insert(cmd, "--exclude")
          table.insert(cmd, entry)
        end
        pick.builtin.cli({ command = cmd }, {
          source = {
            name = "Files",
            cwd = root,
            show = function(buf, items, query)
              pick.default_show(buf, items, query, { show_icons = true })
            end,
          },
        })
      end,
      desc = "Find files",
    },
    {
      "<leader>/",
      function()
        local globs = {
          "!.git",
          "!node_modules",
          "!.venv",
          "!__pycache__",
          "!dist",
          "!build",
          "!.mypy_cache",
          "!.ruff_cache",
          "!staticfiles",
          "!media",
          "!.nuxt",
          "!*.pyc",
          "!*.sqlite3",
        }
        require("mini.pick").builtin.grep_live({ globs = globs }, { source = { cwd = require("util.root").get() } })
      end,
      desc = "Live grep",
    },
    {
      "<leader>,",
      function()
        require("mini.pick").builtin.buffers()
      end,
      desc = "Buffers",
    },
  },
  config = function()
    local function feed(lhs)
      return function()
        vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes(lhs, true, false, true), "n", false)
      end
    end

    require("mini.pick").setup({
      mappings = {
        move_down = "<C-j>",
        move_up = "<C-k>",
        scroll_down = "<C-d>",
        scroll_up = "<C-u>",
        delete_left = "",
        nav_down = { char = "<C-n>", func = feed("<C-j>") },
        nav_up = { char = "<C-p>", func = feed("<C-k>") },
        stop_cq = {
          char = "<C-q>",
          func = function()
            require("mini.pick").stop()
          end,
        },
      },
    })
    require("mini.extra").setup()
  end,
}
