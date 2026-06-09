-- mini.git — git command wrapper + blame. Sourced from the mini.nvim monorepo
-- (shared clone). The standalone echasnovski/mini.git is avoided because its
-- ".git" repo name collides with git's URL suffix convention.
return {
  {
    -- Sourced from the mini.nvim monorepo, NOT the standalone `echasnovski/mini.git`:
    -- the standalone's `.git` repo name collides with git's URL suffix convention
    -- (lazy builds `.../mini.git.git`, which GitHub resolves to a nonexistent `mini`
    -- repo → credential prompt). The monorepo ships the same `mini.git` module.
    "echasnovski/mini.nvim",
    event = "VeryLazy",
    keys = {
      { "<leader>gc", "<cmd>Git commit<cr>", desc = "Git commit" },
      { "<leader>gp", "<cmd>Git pull<cr>", desc = "Git pull" },
      { "<leader>gF", "<cmd>Git push --force-with-lease<cr>", desc = "Git push --force-with-lease" },
      { "<leader>gP", "<cmd>Git push<cr>", desc = "Git push" },
      { "<leader>gf", "<cmd>Git fetch<cr>", desc = "Git fetch" },
      { "<leader>gs", "<cmd>horizontal Git status<cr>", desc = "Git status (panel)" },
      {
        "<leader>gt",
        function()
          local branch = require("util.git").branch()
          if not branch then
            vim.notify("Not on a branch", vim.log.levels.WARN)
            return
          end
          vim.ui.input({ prompt = "Remote tracking branch: ", default = branch }, function(input)
            if not input or input == "" then
              return
            end
            vim.cmd("Git push -u origin " .. input)
          end)
        end,
        desc = "Git push + set upstream tracking (prompt)",
      },
      {
        "<leader>gb",
        function()
          require("mini.git").show_at_cursor()
        end,
        desc = "Git blame line (float)",
      },
      { "<leader>gB", "<cmd>Git blame -- %<cr>", desc = "Git blame (file)" },
      {
        "<leader>gr",
        function()
          -- Open the current branch's PR on GitHub, or start one if none exists.
          vim.system({ "gh", "pr", "view", "--web" }, { text = true }, function(out)
            if out.code ~= 0 then
              vim.system({ "gh", "pr", "create", "--web" })
            end
          end)
        end,
        desc = "Open/create PR on GitHub",
      },
    },
    config = function()
      require("mini.git").setup({})
    end,
  },
}
