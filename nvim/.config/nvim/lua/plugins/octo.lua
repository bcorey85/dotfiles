return {
  "pwntester/octo.nvim",
  opts = {
    -- Don't request GitHub Projects v2 — avoids the
    -- "Missing scope 'read:project'" error on repo fetch.
    -- Set back to true + add the gh scope if you use Projects boards.
    default_to_projects_v2 = false,
    -- Default is 5000ms, which times out on heavy GraphQL queries
    -- like a global `:Octo search`.
    timeout = 20000,
  },
  keys = {
    -- Release octo's default <leader>g* keys. In particular this frees
    -- <leader>gp, which is our fugitive "Git pull" (config/keymaps.lua).
    { "<leader>gi", false },
    { "<leader>gI", false },
    { "<leader>gp", false },
    { "<leader>gP", false },
    { "<leader>gr", false },
    { "<leader>gS", false },

    -- Octo lives under its own <leader>go group instead.
    { "<leader>go", "", desc = "+octo (GitHub)" },
    { "<leader>gop", "<cmd>Octo pr list<cr>", desc = "List PRs (Octo)" },
    { "<leader>goP", "<cmd>Octo pr search<cr>", desc = "Search PRs (Octo)" },
    { "<leader>goi", "<cmd>Octo issue list<cr>", desc = "List Issues (Octo)" },
    { "<leader>goI", "<cmd>Octo issue search<cr>", desc = "Search Issues (Octo)" },
    { "<leader>gor", "<cmd>Octo repo list<cr>", desc = "List Repos (Octo)" },
    {
      "<leader>gos",
      function()
        -- The snacks picker fires `Octo search` against an empty prompt
        -- (i.e. all of GitHub). Ask for the query first and scope it.
        vim.ui.input({ prompt = "Octo search: " }, function(query)
          if query and query ~= "" then
            vim.cmd("Octo search " .. query)
          end
        end)
      end,
      desc = "Search (Octo)",
    },
  },
}
