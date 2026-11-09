-- Copy to the "+" register through a system tool AND an OSC 52 escape. The
-- tool covers the machine nvim runs on; OSC 52 rides the terminal to the
-- machine the user sits at (herdr --remote, ssh), where the tool cannot reach.
local function copy_with_osc52(cmd)
  local osc52_copy = require("vim.ui.clipboard.osc52").copy("+")
  return function(lines, regtype)
    local text = table.concat(lines, "\n")
    vim.system(cmd, { stdin = text })
    osc52_copy(lines, regtype)
  end
end

local function detect_clipboard()
  local uname = vim.uv.os_uname()
  local sysname = uname.sysname

  if sysname == "Darwin" then
    return {
      name = "macOS-clipboard",
      copy = {
        ["+"] = "pbcopy",
        ["*"] = "pbcopy",
      },
      paste = {
        ["+"] = "pbpaste",
        ["*"] = "pbpaste",
      },
    }
  elseif sysname == "Linux" then
    local proc_version = io.open("/proc/version", "r")
    local is_wsl = false
    if proc_version then
      local content = proc_version:read("*a")
      proc_version:close()
      is_wsl = content:lower():find("microsoft") ~= nil or content:lower():find("wsl") ~= nil
    end

    if is_wsl then
      return {
        name = "win32yank-wsl",
        copy = {
          ["+"] = "win32yank.exe -i --crlf",
          ["*"] = "win32yank.exe -i --crlf",
        },
        paste = {
          ["+"] = "win32yank.exe -o --lf",
          ["*"] = "win32yank.exe -o --lf",
        },
      }
    else
      if vim.fn.executable("wl-copy") == 1 then
        return {
          name = "wl-clipboard",
          copy = {
            ["+"] = copy_with_osc52({ "wl-copy" }),
            ["*"] = "wl-copy --primary",
          },
          paste = {
            ["+"] = "wl-paste --no-newline",
            ["*"] = "wl-paste --primary --no-newline",
          },
        }
      elseif vim.fn.executable("xclip") == 1 then
        return {
          name = "xclip",
          copy = {
            ["+"] = copy_with_osc52({ "xclip", "-selection", "clipboard" }),
            ["*"] = "xclip -selection primary",
          },
          paste = {
            ["+"] = "xclip -selection clipboard -o",
            ["*"] = "xclip -selection primary -o",
          },
        }
      else
        return {
          name = "xsel",
          copy = {
            ["+"] = "xsel --clipboard --input",
            ["*"] = "xsel --primary --input",
          },
          paste = {
            ["+"] = "xsel --clipboard --output",
            ["*"] = "xsel --primary --output",
          },
        }
      end
    end
  end

  return {}
end

local cb = detect_clipboard()
-- Cache clipboard reads so a paste doesn't re-spawn the provider binary every
-- time. Critical on WSL where the provider is win32yank.exe over the interop
-- boundary (slow) and with clipboard=unnamedplus every yank/paste hits it.
-- Must set on the local table before assignment: vim.g returns a copy, so
-- mutating a field after assignment is a no-op (see :h lua-vim-variables).
cb.cache_enabled = 1
vim.g.clipboard = cb
