-- Editable file-system buffer drawn as a tree: a right sidebar on <leader>e, and
-- full-window in the herdr `prefix e` popup (FYLER_POPUP).

-- fyler's follow_current_file skips files directly under the root, which is
-- always where the current file sits here. Top-level lines read "<icon> /<id> <name>".
local function put_cursor_on_entry(finder, file)
  local entry_pattern = "^%S+ /%d+ " .. vim.pesc(vim.fs.basename(file)) .. "$"
  finder:refresh({
    callback = function()
      for lnum, line in ipairs(vim.api.nvim_buf_get_lines(finder.buf_id, 0, -1, false)) do
        if line:match(entry_pattern) and vim.api.nvim_win_is_valid(finder.win_id) then
          vim.api.nvim_win_set_cursor(finder.win_id, { lnum, 0 })
          return
        end
      end
    end,
  })
end

-- Opens rooted at the current file's directory every time. A reused finder
-- keeps whatever root `-`/`.` left it at, so visit resets it.
local function toggle_at_current_file()
  local fyler = require("fyler")
  if fyler.getcwd() then
    fyler.close()
    return
  end

  local file = vim.api.nvim_buf_get_name(0)
  local has_file = vim.bo.buftype == "" and file ~= ""
  local dir = has_file and vim.fs.dirname(file) or vim.fn.getcwd()
  fyler.open({ kind = "split_right_most", root_path = dir })

  local finder = require("fyler.finder").instance_get_or_nil()
  if finder then
    finder:visit({ path = dir })
    if has_file then
      put_cursor_on_entry(finder, file)
    end
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
-- manager.
local function open_in_file_manager(finder)
  local entry = require("fyler.finder").parse_cursor_line(finder)
  require("util.file_manager").reveal(entry and entry.path or finder.state.pseudo_root_path)
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
        ["<A-o>"] = { action = open_in_file_manager, desc = "Open in file manager" },
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
