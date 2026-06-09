-- mini.git — git command wrapper + blame. Sourced from the mini.nvim monorepo
-- (shared clone). The standalone echasnovski/mini.git is avoided because its
-- ".git" repo name collides with git's URL suffix convention.
return {
  src = "echasnovski/mini.nvim",
  setup = function()
    require("mini.git").setup({})

    local map = function(lhs, rhs, desc)
      vim.keymap.set("n", lhs, rhs, { desc = desc })
    end

    map("<leader>gc", "<cmd>Git commit<cr>", "Git commit")
    map("<leader>gp", "<cmd>Git pull<cr>", "Git pull")
    map("<leader>gF", "<cmd>Git push --force-with-lease<cr>", "Git push --force-with-lease")
    map("<leader>gP", "<cmd>Git push<cr>", "Git push")
    map("<leader>gf", "<cmd>Git fetch<cr>", "Git fetch")
    map("<leader>gs", "<cmd>horizontal Git status<cr>", "Git status (panel)")
    map("<leader>gt", function()
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
    end, "Git push + set upstream tracking (prompt)")
    map("<leader>gb", function()
      require("mini.git").show_at_cursor()
    end, "Git blame line (float)")
    map("<leader>gB", "<cmd>Git blame -- %<cr>", "Git blame (file)")
    map("<leader>gr", function()
      -- Open the current branch's PR on GitHub, or start one if none exists.
      vim.system({ "gh", "pr", "view", "--web" }, { text = true }, function(out)
        if out.code ~= 0 then
          vim.system({ "gh", "pr", "create", "--web" })
        end
      end)
    end, "Open/create PR on GitHub")
  end,
}
