local watchers = {}

local function watch_buffer(buf)
  local path = vim.api.nvim_buf_get_name(buf)
  if path == "" or watchers[buf] then
    return
  end

  local event = vim.uv.new_fs_event()
  if not event then
    return
  end

  event:start(path, {}, vim.schedule_wrap(function(err)
    if err then
      event:stop()
      if not event:is_closing() then
        event:close()
      end
      watchers[buf] = nil
      return
    end
    if vim.api.nvim_buf_is_valid(buf) then
      vim.api.nvim_buf_call(buf, function()
        vim.cmd("checktime")
      end)
    end
  end))

  watchers[buf] = event
end

vim.api.nvim_create_autocmd("BufReadPost", {
  callback = function(args)
    watch_buffer(args.buf)
  end,
})

vim.api.nvim_create_autocmd("BufDelete", {
  callback = function(args)
    local w = watchers[args.buf]
    if w then
      w:stop()
      if not w:is_closing() then
        w:close()
      end
      watchers[args.buf] = nil
    end
  end,
})

vim.api.nvim_create_autocmd("VimLeavePre", {
  callback = function()
    for buf, w in pairs(watchers) do
      pcall(function()
        w:stop()
        if not w:is_closing() then
          w:close()
        end
      end)
      watchers[buf] = nil
    end
  end,
})

for _, buf in ipairs(vim.api.nvim_list_bufs()) do
  if vim.api.nvim_buf_is_loaded(buf) then
    watch_buffer(buf)
  end
end

vim.api.nvim_create_autocmd(
  { "CursorHold", "CursorHoldI" },
  {
    callback = function()
      vim.cmd("checktime")
    end,
  }
)

vim.api.nvim_create_autocmd("FileType", {
  pattern = { "markdown", "text", "gitcommit" },
  callback = function()
    vim.opt_local.wrap = true
    vim.opt_local.linebreak = true
  end,
})

vim.api.nvim_create_autocmd("FileChangedShellPost", {
  callback = function(args)
    local buf = args.buf
    for _, client in pairs(vim.lsp.get_clients({ bufnr = buf })) do
      local version = (vim.lsp.util.buf_versions[buf] or 0) + 1
      vim.lsp.util.buf_versions[buf] = version
      client:notify("textDocument/didChange", {
        textDocument = {
          uri = vim.uri_from_bufnr(buf),
          version = version,
        },
        contentChanges = {
          { text = table.concat(vim.api.nvim_buf_get_lines(buf, 0, -1, false), "\n") .. "\n" },
        },
      })
    end
  end,
})

vim.api.nvim_create_autocmd("TextYankPost", {
  callback = function()
    vim.highlight.on_yank()
  end,
})

vim.api.nvim_create_autocmd("VimResized", {
  callback = function()
    local current_tab = vim.fn.tabpagenr()
    vim.cmd("tabdo wincmd =")
    vim.cmd("tabnext " .. current_tab)
  end,
})

vim.api.nvim_create_autocmd("BufReadPost", {
  callback = function(args)
    local mark = vim.api.nvim_buf_get_mark(args.buf, '"')
    local lcount = vim.api.nvim_buf_line_count(args.buf)
    if mark[1] > 0 and mark[1] <= lcount then
      pcall(vim.api.nvim_win_set_cursor, 0, mark)
    end
  end,
})
