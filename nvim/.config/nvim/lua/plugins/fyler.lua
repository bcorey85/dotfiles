-- Editable file-system buffer drawn as a tree: a left sidebar on <leader>e, and
-- full-window in the herdr `prefix e` popup (FYLER_POPUP).

-- Opens rooted at the current file's directory every time. A reused finder
-- keeps whatever root `-`/`.` left it at, so visit resets it.
local function toggle_at_current_file()
  local fyler = require("fyler")
  if fyler.getcwd() then
    fyler.close()
    return
  end

  local file = vim.api.nvim_buf_get_name(0)
  local dir = (vim.bo.buftype == "" and file ~= "") and vim.fs.dirname(file) or vim.fn.getcwd()
  fyler.open({ kind = "split_left_most", root_path = dir })

  local finder = require("fyler.finder").instance_get_or_nil()
  if finder then
    finder:visit({ path = dir })
  end
end

-- fyler has no collapse-all action; state.meta holds each directory's
-- expanded flag, so clear it and keep only the root open.
local function collapse_all(finder)
  for dir_key in pairs(finder.state.meta) do
    finder.state.meta[dir_key] = false
  end
  finder.state:toggle(finder.state.pseudo_root_path, true)
  finder:refresh()
end

-- Opens the entry under the cursor (the root on a blank line) in the OS file
-- manager. On macOS a file is revealed in its folder (`open -R`).
local function open_in_file_manager(finder)
  local entry = require("fyler.finder").parse_cursor_line(finder)
  local target = entry and entry.path or finder.state.pseudo_root_path
  local is_dir = not entry or entry.type == "directory"

  local cmd
  if vim.fn.has("mac") == 1 then
    cmd = is_dir and { "open", target } or { "open", "-R", target }
  else
    cmd = { "thunar", target }
  end
  vim.fn.jobstart(cmd, { detach = true })
end

return {
  "FylerOrg/fyler.nvim",
  keys = {
    { "<leader>e", toggle_at_current_file, desc = "Fyler sidebar (file's dir)" },
  },
  cmd = { "Fyler" },
  init = function()
    -- mini.clue doesn't install its prefix triggers in fyler's buffer-local
    -- maps, so `g`/`z` chords (g., gi, gO, zM) fall back to timeoutlen.
    -- Re-arm them per fyler buffer.
    vim.api.nvim_create_autocmd("FileType", {
      pattern = "fyler_finder",
      callback = function(args)
        require("mini.clue").ensure_buf_triggers(args.buf)
      end,
    })
  end,
  opts = {
    use_as_default_explorer = false,
    -- Default tcd's to the finder root, which would move snacks pickers' cwd.
    follow_root_dir = false,
    integrations = { icon = "mini_icons" },
    extensions = {
      git = { enabled = true },
      watcher = { enabled = true },
    },
    -- Show dotfiles.
    ui = { hidden_items = { switches = {} } },
    mappings = {
      n = {
        ["zM"] = { action = collapse_all, desc = "Collapse all directories" },
        ["gO"] = { action = open_in_file_manager, desc = "Open in file manager" },
        -- herdr `prefix e` popup: the whole nvim is disposable, so q quits it.
        -- Only fyler's own q is remapped: files opened from the popup are
        -- editable, and a global q would eat macro recording. `qa` without
        -- bang: unsaved buffers still block the quit.
        ["q"] = vim.env.FYLER_POPUP and {
          action = function()
            vim.cmd("qa")
          end,
          desc = "Close fyler popup",
        } or nil,
      },
    },
  },
}
