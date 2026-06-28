-- Drives nvim-orgmode capture / agenda for the `org-popup` script (tmux
-- display-popup). Entry points: M.capture(shortcut?) and M.agenda(). Launched as
-- `nvim -c "lua require('util.org_popup').capture()"` in a throwaway nvim, so it
-- owns the whole instance and quits it when you're done.
local M = {}

local function close_popup()
  vim.schedule(function()
    pcall(vim.cmd, "qa!")
  end)
end

-- Throwaway popup: never use swap files, and never prompt about a target file's
-- existing swap (it's normal for the target, e.g. inbox.org, to be open in your
-- main editor). shortmess+=A suppresses the ATTENTION swap prompt that would
-- otherwise block the popup's clean open/close.
local function quiet_throwaway()
  vim.opt.swapfile = false
  vim.opt.shortmess:append("A")
end

-- The capture buffer is tagged with b:org_capture_window_id.
local function is_capture_buf(buf)
  return buf
    and vim.api.nvim_buf_is_valid(buf)
    and (pcall(vim.api.nvim_buf_get_var, buf, "org_capture_window_id"))
end

-- Popup-local capture keys. We override org's native finalize because driving it
-- indirectly (stopinsert/defer) let the native <C-c> ALSO fire against a
-- half-closed window -> E5108 (nil capture_window). capture.refile, called
-- directly and synchronously, appends the entry to its target file on disk
-- regardless of whether it also wipes the buffer — so it's always safe to close
-- the popup right after.
--   <C-c> (insert or normal) -> file to the template target, then close
--   q     (normal)           -> close/discard without saving
local function setup_capture_keys(buf)
  vim.keymap.set({ "i", "n" }, "<C-c>", function()
    require("orgmode").action("capture.refile") -- writes the entry to its target file
    close_popup() -- qa! (force) skips the throwaway capture-buffer save prompt
  end, { buffer = buf, desc = "org: file capture & close" })

  vim.keymap.set("n", "q", function()
    -- org's clean abort: closes without saving and without the "refile this?"
    -- prompt a raw :qa! on a modified capture buffer would trigger.
    pcall(require("orgmode").action, "capture.kill", true)
    close_popup() -- backstop if kill didn't already quit the (single-window) popup
  end, { buffer = buf, desc = "org: close capture (discard)" })
end

function M.capture(shortcut)
  quiet_throwaway()
  -- Open in the current window (fills the popup) instead of a split. Per-process
  -- override; the user's in-editor win_split_mode is untouched.
  require("orgmode.config").opts.win_split_mode = "edit"

  -- Backstop: if the capture buffer is wiped by any other path, close the popup.
  vim.api.nvim_create_autocmd("BufWipeout", {
    callback = function(a)
      if is_capture_buf(a.buf) then
        close_popup()
      end
    end,
  })
  vim.api.nvim_create_autocmd("BufWinEnter", {
    callback = function(a)
      vim.defer_fn(function()
        if is_capture_buf(a.buf) then
          setup_capture_keys(a.buf)
        end
      end, 30)
    end,
  })

  vim.schedule(function()
    if shortcut and shortcut ~= "" then
      require("orgmode").action("capture.open_template_by_shortcut", shortcut)
    else
      -- The t/n/j selection menu (blocking getchar). If dismissed without
      -- choosing a template, no capture buffer opens — so close the popup.
      require("orgmode").action("capture.prompt")
      vim.defer_fn(function()
        for _, b in ipairs(vim.api.nvim_list_bufs()) do
          if is_capture_buf(b) then
            return
          end
        end
        close_popup()
      end, 50)
    end
  end)
end

function M.agenda()
  quiet_throwaway()
  -- Fullscreen single window. Note: org's own `q` does nvim_win_close on the
  -- current window, which can't close the LAST window — so in a single-window
  -- popup it silently does nothing. We override `q` in the agenda buffer to quit
  -- the whole popup instead. (Safe: you don't record macros in the agenda.)
  require("orgmode.config").opts.win_split_mode = "edit"

  vim.api.nvim_create_autocmd("FileType", {
    pattern = "orgagenda",
    callback = function(a)
      -- Defer so we win over org's own `q` map (set during agenda render).
      vim.defer_fn(function()
        if vim.api.nvim_buf_is_valid(a.buf) then
          vim.keymap.set("n", "q", close_popup, { buffer = a.buf, desc = "org: close agenda popup" })
        end
      end, 50)
    end,
  })

  vim.schedule(function()
    require("orgmode").action("agenda.agenda")
  end)
end

return M
