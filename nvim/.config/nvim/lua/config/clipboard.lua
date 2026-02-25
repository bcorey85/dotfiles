-- Detect OS and configure clipboard accordingly
local function detect_clipboard()
  local uname = vim.loop.os_uname()
  local sysname = uname.sysname

  if sysname == "Darwin" then
    -- macOS
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
    -- Check if running in WSL
    local proc_version = io.open("/proc/version", "r")
    local is_wsl = false
    if proc_version then
      local content = proc_version:read("*a")
      proc_version:close()
      is_wsl = content:lower():find("microsoft") ~= nil or content:lower():find("wsl") ~= nil
    end

    if is_wsl then
      -- WSL2
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
      -- Native Linux - try wl-copy (Wayland), then xclip, then xsel
      if os.execute("command -v wl-copy > /dev/null 2>&1") == 0 then
        return {
          name = "wl-clipboard",
          copy = {
            ["+"] = "wl-copy",
            ["*"] = "wl-copy --primary",
          },
          paste = {
            ["+"] = "wl-paste --no-newline",
            ["*"] = "wl-paste --primary --no-newline",
          },
        }
      elseif os.execute("command -v xclip > /dev/null 2>&1") == 0 then
        return {
          name = "xclip",
          copy = {
            ["+"] = "xclip -selection clipboard",
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

  -- Fallback (shouldn't reach here)
  return {}
end

vim.g.clipboard = detect_clipboard()
vim.g.clipboard.cache_enabled = 0
