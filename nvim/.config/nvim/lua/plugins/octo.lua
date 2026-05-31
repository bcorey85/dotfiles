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
    mappings = {
      review_diff = {
        toggle_viewed = { lhs = "<leader>gv", desc = "toggle viewed" },
        select_next_unviewed_entry = { lhs = "]r", desc = "next unviewed file" },
        select_prev_unviewed_entry = { lhs = "[r", desc = "prev unviewed file" },
      },
      file_panel = {
        toggle_viewed = { lhs = "<leader>gv", desc = "toggle viewed" },
        select_next_unviewed_entry = { lhs = "]r", desc = "next unviewed file" },
        select_prev_unviewed_entry = { lhs = "[r", desc = "prev unviewed file" },
      },
    },
  },
  keys = {
    { "<leader>gh", "", desc = "+github (Octo)" },
    {
      "<leader>ghv",
      function()
        local url = vim.fn.getreg("+"):gsub("%s+", "")
        if not url:match("^https?://.*github") then
          Snacks.notify.warn("Clipboard doesn't look like a GitHub URL: " .. url)
          return
        end
        vim.cmd("Octo " .. url)
      end,
      desc = "Open URL from clipboard (Octo)",
    },
    { "<leader>ghc", "<cmd>Octo pr create<cr>", desc = "Create PR (Octo)" },
    { "<leader>gho", "<cmd>Octo pr checkout<cr>", desc = "Checkout PR locally (Octo)" },
    { "<leader>ghp", "<cmd>Octo pr list<cr>", desc = "List PRs (Octo)" },
    { "<leader>ghP", octo_prompt("Octo PR search: ", "Octo pr search"), desc = "Search PRs (Octo)" },
    { "<leader>ghi", "<cmd>Octo issue list<cr>", desc = "List Issues (Octo)" },
    { "<leader>ghI", octo_prompt("Octo issue search: ", "Octo issue search"), desc = "Search Issues (Octo)" },
    { "<leader>ghr", octo_prompt("Repos for (blank = you): ", "Octo repo list", true), desc = "List Repos (Octo)" },
    { "<leader>ghs", octo_prompt("Octo search: ", "Octo search"), desc = "Search (Octo)" },
    {
      "<leader>ghb",
      function() require("octo.navigation").open_in_browser() end,
      desc = "Open current PR/issue in browser (Octo)",
    },

    -- Review / comments / threads (all under <leader>gr*)
    { "<leader>gr", "", desc = "+review (Octo)" },
    { "<leader>grs", "<cmd>Octo review start<cr>", desc = "Review: start" },
    { "<leader>grc", "<cmd>Octo review resume<cr>", desc = "Review: continue" },
    { "<leader>grx", "<cmd>Octo review submit<cr>", desc = "Review: submit" },
    { "<leader>grd", "<cmd>Octo review discard<cr>", desc = "Review: discard" },
    { "<leader>grp", "<cmd>Octo review comments<cr>", desc = "Review: pending comments" },
    { "<leader>gra", "<cmd>Octo comment add<cr>", mode = { "n", "v" }, desc = "Comment: add" },
    { "<leader>gre", "<cmd>Octo comment edit<cr>", desc = "Comment: edit" },
    { "<leader>grk", "<cmd>Octo comment delete<cr>", desc = "Comment: kill (delete)" },
    { "<leader>grt", "<cmd>Octo thread resolve<cr>", desc = "Thread: resolve" },
    { "<leader>gru", "<cmd>Octo thread unresolve<cr>", desc = "Thread: unresolve" },
  },
}
