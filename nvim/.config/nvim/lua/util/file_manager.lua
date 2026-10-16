-- Opens a path in the OS file manager: fyler's gO and the snacks pickers' <a-o>.
-- On macOS a file is revealed in its folder (`open -R`). Without thunar
-- (WSL/Ubuntu), vim.ui.open opens the file's folder.
local M = {}

function M.reveal(path)
  local is_dir = vim.fn.isdirectory(path) == 1
  if vim.fn.has("mac") == 1 then
    vim.fn.jobstart(is_dir and { "open", path } or { "open", "-R", path }, { detach = true })
  elseif vim.fn.executable("thunar") == 1 then
    vim.fn.jobstart({ "thunar", path }, { detach = true })
  else
    vim.ui.open(is_dir and path or vim.fs.dirname(path))
  end
end

return M
