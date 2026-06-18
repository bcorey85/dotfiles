-- Buffer path helpers. Pure (no UI side effects) so callers own how they report
-- the unnamed-buffer case. Lives here, not as a local in keymaps.lua, so it's
-- discoverable: review.lua already independently reinvented "current file or
-- bail" once — the next file should find this instead of writing a third copy.
local M = {}

-- Raw name of a buffer (current by default), or nil if it has no file name.
-- May be relative — callers that need the path resolved against a base do that
-- themselves (see review.lua's repo-root resolution).
function M.name(buf)
  local n = vim.api.nvim_buf_get_name(buf or 0)
  return n ~= "" and n or nil
end

-- Absolute path of a buffer's file (current by default), or nil if unnamed.
function M.path(buf)
  local n = M.name(buf)
  return n and vim.fn.fnamemodify(n, ":p") or nil
end

-- True if a buffer is a normal file buffer (empty 'buftype'), i.e. not a special
-- buffer: help, quickfix, terminal, prompt, or a nofile scratch. The single most
-- reinvented guard in this config — every git/winbar/autocmd hook needs it.
function M.is_file(buf)
  return vim.bo[buf or 0].buftype == ""
end

return M
