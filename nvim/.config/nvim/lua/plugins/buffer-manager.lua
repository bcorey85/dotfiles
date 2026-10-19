-- buffer_manager.nvim — the open buffers as an editable float. Move a line to
-- reorder (J/K), delete a line to close that buffer (applied when the list
-- closes; modified and terminal buffers are kept), <CR> or 1..0 to jump.
-- The order is barbar's tab order: the list opens in it and writes back to it.
local function sort_marks_by_tabs()
  local bm = require("buffer_manager")
  require("buffer_manager.ui").update_marks()
  if not package.loaded["barbar"] then
    return
  end

  local tab_positions = {}
  for position, bufnr in ipairs(require("barbar.state").buffers) do
    tab_positions[bufnr] = position
  end

  local marks = {}
  for list_position, mark in pairs(bm.marks) do
    table.insert(marks, { mark = mark, list_position = list_position })
  end
  table.sort(marks, function(a, b)
    local a_tab = tab_positions[a.mark.buf_id] or math.huge
    local b_tab = tab_positions[b.mark.buf_id] or math.huge
    if a_tab ~= b_tab then
      return a_tab < b_tab
    end
    return a.list_position < b.list_position
  end)

  bm.marks = vim.tbl_map(function(entry)
    return entry.mark
  end, marks)
end

local function sort_tabs_by_marks()
  if not package.loaded["barbar"] then
    return
  end
  local state = require("barbar.state")

  local in_tabs = {}
  for _, bufnr in ipairs(state.buffers) do
    in_tabs[bufnr] = true
  end

  local tab_order = {}
  local placed = {}
  for _, mark in ipairs(require("buffer_manager").marks) do
    if in_tabs[mark.buf_id] then
      table.insert(tab_order, mark.buf_id)
      placed[mark.buf_id] = true
    end
  end
  for _, bufnr in ipairs(state.buffers) do
    if not placed[bufnr] then
      table.insert(tab_order, bufnr)
    end
  end

  state.buffers = tab_order
  state.sort_pins_to_left()
  require("barbar.ui.render").update()
end

return {
  "j-morano/buffer_manager.nvim",
  dependencies = { "nvim-lua/plenary.nvim" },
  keys = {
    {
      "<leader>.",
      function()
        sort_marks_by_tabs()
        require("buffer_manager.ui").toggle_quick_menu()
      end,
      desc = "Buffer list",
    },
  },
  config = function()
    require("buffer_manager").setup({
      select_menu_item_commands = {
        vsplit = { key = "<C-v>", command = "vsplit" },
        split = { key = "<C-s>", command = "split" },
      },
    })

    vim.api.nvim_create_autocmd("FileType", {
      group = vim.api.nvim_create_augroup("BufferManagerReorder", { clear = true }),
      pattern = "buffer_manager",
      callback = function(event)
        local function map(mode, lhs, rhs, desc)
          vim.keymap.set(mode, lhs, rhs, { buffer = event.buf, silent = true, desc = desc })
        end
        map("n", "J", "<cmd>move .+1<cr>", "Move buffer down")
        map("n", "K", "<cmd>move .-2<cr>", "Move buffer up")
        map("x", "J", ":move '>+1<cr>gv", "Move buffers down")
        map("x", "K", ":move '<-2<cr>gv", "Move buffers up")

        -- Scheduled past the plugin's own BufLeave, which saves the list and closes buffers.
        vim.api.nvim_create_autocmd("BufLeave", {
          buffer = event.buf,
          once = true,
          callback = vim.schedule_wrap(sort_tabs_by_marks),
        })
      end,
    })
  end,
}
