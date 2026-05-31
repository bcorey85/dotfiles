local function octo_prompt(label, cmd, allow_empty)
  return function()
    vim.ui.input({ prompt = label }, function(input)
      if input == nil then
        return
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
  -- Pinned: PR #1491 (timeline registry refactor, merged 2026-05-18) introduced
  -- duplicate GraphQL fragments breaking Octo pr create. Unpin once #1520 lands.
  commit = "7566ab21843bf0de721f72891733c0372738d3ee",
  cmd = { "Octo" },
  dependencies = {
    "nvim-lua/plenary.nvim",
    "nvim-tree/nvim-web-devicons",
  },
  opts = {
    picker = "snacks",
    default_to_projects_v2 = false,
    timeout = 20000,
    suppress_missing_scope = {
      projects_v2 = true,
    },
  },
  keys = {
    { "<leader>go", "", desc = "+octo (GitHub)" },
    { "<leader>goc", "<cmd>Octo pr create<cr>", desc = "Create PR (Octo)" },
    { "<leader>gop", "<cmd>Octo pr list<cr>", desc = "List PRs (Octo)" },
    { "<leader>goP", octo_prompt("Octo PR search: ", "Octo pr search"), desc = "Search PRs (Octo)" },
    { "<leader>goi", "<cmd>Octo issue list<cr>", desc = "List Issues (Octo)" },
    { "<leader>goI", octo_prompt("Octo issue search: ", "Octo issue search"), desc = "Search Issues (Octo)" },
    { "<leader>gor", octo_prompt("Repos for (blank = you): ", "Octo repo list", true), desc = "List Repos (Octo)" },
    { "<leader>gos", octo_prompt("Octo search: ", "Octo search"), desc = "Search (Octo)" },
  },
}
