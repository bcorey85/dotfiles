local git_status = require("util.git_status")

local GENERIC_VENV_NAMES = { [".venv"] = true, ["venv"] = true, ["env"] = true }

local function hl_fg(name, fallback)
  local ok, hl = pcall(vim.api.nvim_get_hl, 0, { name = name, link = false })
  if ok and hl.fg then
    return { fg = string.format("#%06x", hl.fg) }
  end
  return { fg = fallback }
end

-- Inverted high-visibility badge (bg text-color on an error-colored block),
-- built from live groups so it holds up across the light/dark toggle.
local function badge_color()
  local bg = hl_fg("DiagnosticError", "#ff0000").fg
  local fg = hl_fg("Normal", "#000000").bg or "#000000"
  return { fg = fg, bg = bg, gui = "bold" }
end

local function venv_label(venv_path)
  local basename = vim.fn.fnamemodify(venv_path, ":t")
  if GENERIC_VENV_NAMES[basename] then
    return vim.fn.fnamemodify(venv_path, ":h:t")
  end
  return basename
end

local function recording()
  local reg = vim.fn.reg_recording()
  return reg ~= "" and ("⏺ REC @" .. reg) or ""
end

local function project()
  return vim.fs.basename(git_status.toplevel() or vim.fn.getcwd())
end

local function readonly()
  return (vim.bo.readonly or not vim.bo.modifiable) and "  " or ""
end

local function venv()
  if vim.bo.filetype ~= "python" then
    return ""
  end
  local v = os.getenv("VIRTUAL_ENV")
  return (v and v ~= "") and (" " .. venv_label(v)) or ""
end

local function ahead_behind()
  local status = git_status.status()
  if not status then
    return ""
  end
  if status.no_upstream then
    local count = (status.stranded and status.stranded > 0) and (status.stranded .. " ") or ""
    return "󰶣 " .. count .. "unpushed"
  end
  if status.ahead == 0 and status.behind == 0 then
    return ""
  end
  local parts = {}
  if status.ahead > 0 then
    parts[#parts + 1] = "↑" .. status.ahead
  end
  if status.behind > 0 then
    parts[#parts + 1] = "↓" .. status.behind
  end
  return table.concat(parts, " ")
end

local function ahead_behind_color()
  local status = git_status.status()
  if not status then
    return nil
  end
  if status.no_upstream or status.ahead > 0 then
    return hl_fg("DiagnosticWarn", "#ffaa00")
  end
  if status.behind > 0 then
    return hl_fg("DiagnosticHint", "#00afaf")
  end
  return nil
end

return {
  src = "nvim-lualine/lualine.nvim",
  setup = function()
    require("lualine").setup({
      options = {
        theme = "auto",
        component_separators = "",
        section_separators = "",
        globalstatus = true,
      },
      sections = {
        lualine_a = { { recording, color = "DiagnosticError" } },
        lualine_b = { project },
        lualine_c = {
          { "branch", icon = "", color = { gui = "bold" } },
          { readonly, color = badge_color },
        },
        lualine_x = {
          { "searchcount", maxcount = 999, icon = "\xF3\xB0\x8D\x89" },
          { "%S", type = "stl" }, -- native pending-count/operator readout (showcmd)
          "lsp_status",
        },
        lualine_y = { venv },
        lualine_z = {
          { "diagnostics", sections = { "error", "warn" }, symbols = { error = " ", warn = " " } },
          { ahead_behind, color = ahead_behind_color },
        },
      },
      inactive_sections = {},
    })

    -- Instant feedback for macro recording (lualine's default periodic
    -- refresh would otherwise lag the indicator by up to a second).
    vim.api.nvim_create_autocmd({ "RecordingEnter", "RecordingLeave" }, {
      group = vim.api.nvim_create_augroup("LualineRecording", { clear = true }),
      callback = function()
        vim.schedule(function()
          require("lualine").refresh()
        end)
      end,
    })
  end,
}
