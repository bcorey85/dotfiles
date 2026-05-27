-- The snacks picker doesn't implement octo's live search prompt, so the
-- search/list-by-owner commands would otherwise fire against an empty prompt
-- (e.g. all of GitHub). This helper supplies the missing input box.
--   allow_empty = true -> run even with no input (command has a safe default).
local function octo_prompt(label, cmd, allow_empty)
  return function()
    vim.ui.input({ prompt = label }, function(input)
      if input == nil then
        return -- cancelled
      end
      if input == "" and not allow_empty then
        return
      end
      vim.cmd(cmd .. " " .. input)
    end)
  end
end

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
    { "<leader>goP", octo_prompt("Octo PR search: ", "Octo pr search"), desc = "Search PRs (Octo)" },
    { "<leader>goi", "<cmd>Octo issue list<cr>", desc = "List Issues (Octo)" },
    { "<leader>goI", octo_prompt("Octo issue search: ", "Octo issue search"), desc = "Search Issues (Octo)" },
    -- Blank input -> your own repos (octo's default); type an org/user to scope.
    { "<leader>gor", octo_prompt("Repos for (blank = you): ", "Octo repo list", true), desc = "List Repos (Octo)" },
    { "<leader>gos", octo_prompt("Octo search: ", "Octo search"), desc = "Search (Octo)" },
  },
}
