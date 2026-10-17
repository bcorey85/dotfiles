-- `nvim-jump --note`: shade the jumped-to lines and show the agent's note above
-- them as virtual lines, re-wrapped when the window resizes. nvim-jump sends a
-- list of locations; ]k/[k step through it, and the next nvim-jump replaces it.
-- One note at a time; <Esc> in that buffer dismisses it. nvim-jump calls show()
-- over RPC right after its :edit, so the first location is the current buffer.
local M = {}

local ns = vim.api.nvim_create_namespace("nvim_jump_note")
local jumps ---@type { file: string, first: integer, last: integer, note: string }[]|nil
local position = 0
local shown ---@type { buf: integer, first: integer, last: integer, label: string|nil, note: string }|nil

-- Mix two 0xRRGGBB colors; alpha is fg's share.
local function blend(fg, bg, alpha)
  local mixed = 0
  for _, scale in ipairs({ 65536, 256, 1 }) do
    local fg_channel, bg_channel = math.floor(fg / scale) % 256, math.floor(bg / scale) % 256
    mixed = mixed + math.floor(fg_channel * alpha + bg_channel * (1 - alpha) + 0.5) * scale
  end
  return mixed
end

-- The note is a fixed orange, a hue no syntax group uses: orange text on an
-- orange-tinted band in dark mode, dark text on solid orange in light mode.
local orange = 0xe9a066
require("util.hl").register("NvimJumpNoteHl", function()
  local normal = vim.api.nvim_get_hl(0, { name = "Normal", link = false })
  local note = vim.o.background == "light" and { fg = normal.fg or 0x000000, bg = orange }
    or { fg = orange, bg = blend(orange, normal.bg or 0x000000, 0.2) }
  note.bold = true
  return {
    NvimJumpRange = { link = "LspReferenceText" },
    NvimJumpNote = note,
  }
end)

-- Word-wrap each of the note's own lines to `width` display columns.
local function wrap(note, width)
  local wrapped = {}
  for paragraph in vim.gsplit(note, "\n", { plain = true }) do
    local line = ""
    for word in paragraph:gmatch("%S+") do
      local candidate = line == "" and word or line .. " " .. word
      if line ~= "" and vim.fn.strdisplaywidth(candidate) > width then
        table.insert(wrapped, line)
        line = word
      else
        line = candidate
      end
    end
    table.insert(wrapped, line)
  end
  return wrapped
end

local function render()
  local win = vim.fn.bufwinid(shown.buf)
  if win == -1 then
    return
  end
  vim.api.nvim_buf_clear_namespace(shown.buf, ns, 0, -1)
  for row = shown.first - 1, shown.last - 1 do
    vim.api.nvim_buf_set_extmark(shown.buf, ns, row, 0, { line_hl_group = "NvimJumpRange" })
  end
  local indent = vim.api.nvim_buf_call(shown.buf, function()
    return vim.fn.indent(shown.first)
  end)
  local badge = shown.label and (" %s "):format(shown.label) or ""
  local hang = string.rep(" ", vim.fn.strdisplaywidth(badge))
  local block_width = vim.api.nvim_win_get_width(win) - vim.fn.getwininfo(win)[1].textoff - indent - #hang
  local note_lines = {}
  for i, line in ipairs(wrap(shown.note, math.max(block_width - 2, 20))) do
    local body = " " .. line
    table.insert(note_lines, {
      { string.rep(" ", indent) },
      { i == 1 and badge or hang, "NvimJumpNote" },
      { body .. string.rep(" ", block_width - vim.fn.strdisplaywidth(body)), "NvimJumpNote" },
    })
  end
  vim.api.nvim_buf_set_extmark(shown.buf, ns, shown.first - 1, 0, { virt_lines = note_lines, virt_lines_above = true })
  -- Virtual lines above line 1 stay hidden until 'topfill' makes room for them.
  if shown.first == 1 then
    for _, buf_win in ipairs(vim.fn.win_findbuf(shown.buf)) do
      vim.api.nvim_win_call(buf_win, function()
        if vim.fn.line("w0") == 1 then
          vim.fn.winrestview({ topfill = #note_lines })
        end
      end)
    end
  end
end

vim.api.nvim_create_autocmd("WinResized", {
  group = vim.api.nvim_create_augroup("NvimJumpNote", { clear = true }),
  callback = function()
    if shown and vim.api.nvim_buf_is_valid(shown.buf) then
      render()
    end
  end,
})

local function is_current_file(file)
  return vim.uv.fs_realpath(vim.api.nvim_buf_get_name(0)) == vim.uv.fs_realpath(file)
end

function M.clear()
  if shown and vim.api.nvim_buf_is_valid(shown.buf) then
    vim.api.nvim_buf_clear_namespace(shown.buf, ns, 0, -1)
    pcall(vim.keymap.del, "n", "<Esc>", { buffer = shown.buf })
  end
  shown = nil
end

-- Shade and annotate jumps[position] in the current buffer; a list labels its
-- note with the position. Returns "" when done, else why nothing was shown.
local function show_current()
  M.clear()
  local jump = jumps[position]
  local label = #jumps > 1 and ("%d/%d"):format(position, #jumps) or nil
  local note = vim.trim(jump.note)
  if not label and note == "" then
    return ""
  end
  if not is_current_file(jump.file) then
    return "current buffer is not " .. jump.file
  end
  local buf = vim.api.nvim_get_current_buf()
  local line_count = vim.api.nvim_buf_line_count(buf)
  local first = math.min(jump.first, line_count)
  shown = { buf = buf, first = first, last = math.min(math.max(jump.last, first), line_count), label = label, note = note }
  render()
  vim.keymap.set("n", "<Esc>", function()
    M.clear()
    vim.api.nvim_feedkeys(vim.keycode("<Esc>"), "m", false)
  end, { buffer = buf, desc = "Clear nvim-jump note" })
  return ""
end

-- new_jumps: the { file, first, last, note } list from nvim-jump, which has
-- already opened the first. Returns "" when done, else why no note was shown.
function M.show(new_jumps)
  jumps, position = new_jumps, 1
  return show_current()
end

-- Open the location `delta` steps along the list and show its note.
function M.step(delta)
  if not jumps then
    vim.notify("No nvim-jump locations", vim.log.levels.INFO)
    return
  end
  local target = position + delta
  if target < 1 or target > #jumps then
    vim.notify(("nvim-jump: %s of %d"):format(target < 1 and "first" or "last", #jumps), vim.log.levels.INFO)
    return
  end
  position = target
  local jump = jumps[position]
  vim.cmd("normal! m'")
  if not is_current_file(jump.file) then
    vim.cmd("edit " .. vim.fn.fnameescape(jump.file))
  end
  vim.api.nvim_win_set_cursor(0, { math.min(jump.first, vim.api.nvim_buf_line_count(0)), 0 })
  vim.cmd("normal! zz")
  show_current()
end

return M
