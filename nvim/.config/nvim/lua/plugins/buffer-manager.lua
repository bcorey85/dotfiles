-- buffer_manager.nvim — the open buffers as an editable float. Move a line to
-- reorder (J/K), delete a line to close that buffer (applied when the list
-- closes; modified and terminal buffers are kept), <CR> or 1..0 to jump.
-- <leader>1..4 jump by list position. The order lasts for the session.
local function nav_slot(slot)
  return function()
    require("buffer_manager.ui").nav_file(slot)
  end
end

return {
  "j-morano/buffer_manager.nvim",
  dependencies = { "nvim-lua/plenary.nvim" },
  keys = {
    { "<leader>.", function() require("buffer_manager.ui").toggle_quick_menu() end, desc = "Buffer list" },
    { "<leader>1", nav_slot(1), desc = "Buffer 1" },
    { "<leader>2", nav_slot(2), desc = "Buffer 2" },
    { "<leader>3", nav_slot(3), desc = "Buffer 3" },
    { "<leader>4", nav_slot(4), desc = "Buffer 4" },
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
      end,
    })
  end,
}
