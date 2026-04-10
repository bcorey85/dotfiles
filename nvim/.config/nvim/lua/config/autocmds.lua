-- Watch open buffers for external file changes using fs_event (no polling)
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
      watchers[args.buf] = nil
    end
  end,
})

-- Watch any already-open buffers
for _, buf in ipairs(vim.api.nvim_list_bufs()) do
  if vim.api.nvim_buf_is_loaded(buf) then
    watch_buffer(buf)
  end
end

-- Fallback: check for external changes on idle (covers tmux pane switches)
vim.api.nvim_create_autocmd(
  { "CursorHold", "CursorHoldI" },
  {
    callback = function()
      vim.cmd("checktime")
    end,
  }
)

-- Force LSP to re-analyze after external file changes reload the buffer
-- vtsls doesn't re-publish diagnostics on didClose+didOpen from checktime
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
