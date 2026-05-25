return {
  "tpope/vim-fugitive",
  cmd = { "Git", "G", "Gdiffsplit", "Gvdiffsplit", "Gread", "Gwrite", "Gedit", "GBrowse" },
  config = function()
    local group = vim.api.nvim_create_augroup("FugitiveBufferKeys", { clear = true })
    vim.api.nvim_create_autocmd("BufWinEnter", {
      group = group,
      pattern = "*",
      callback = function()
        if vim.bo.ft ~= "fugitive" then
          return
        end
        local opts = { buffer = vim.api.nvim_get_current_buf(), remap = false, silent = true }
        vim.keymap.set("n", "<leader>p", function() vim.cmd.Git("push") end,
          vim.tbl_extend("force", opts, { desc = "Git push" }))
        vim.keymap.set("n", "<leader>P", function() vim.cmd.Git({ "pull", "--rebase" }) end,
          vim.tbl_extend("force", opts, { desc = "Git pull --rebase" }))
        vim.keymap.set("n", "<leader>t", ":Git push -u origin ",
          vim.tbl_extend("force", opts, { silent = false, desc = "Git push -u origin <branch>" }))
      end,
    })
  end,
}
