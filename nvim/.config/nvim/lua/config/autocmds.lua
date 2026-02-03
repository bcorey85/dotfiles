-- BufEnter + CursorHold is enough, skip CursorMoved and the timer
vim.api.nvim_create_autocmd({ "BufEnter", "CursorHold" }, {
  callback = function()
    if vim.fn.getcmdwintype() == "" and vim.o.buftype ~= "nofile" then
      vim.cmd("checktime")
    end
  end,
})

vim.o.updatetime = 250

vim.api.nvim_create_autocmd("TermOpen", {
  callback = function()
    vim.opt_local.wrap = true
  end,
})
