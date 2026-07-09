-- theme-sync — keep nvim in sync with the shared theme state written by the
-- `theme-mode` script (scripts/.local/bin/theme-mode):
--   ~/.cache/theme-mode    "dark" | "light"
--   ~/.cache/theme-family  family name (FAMILIES below)
-- Both files are fs_poll'ed (~1s), so `theme-mode use github` or a prefix T
-- toggle from tmux flips every running instance with no sockets to manage.
-- <leader>ut shells out to the same script, so a toggle from nvim flips tmux
-- and ghostty too — one source of truth, all ways.
--
-- This module also owns every theme-reactive highlight override (markview
-- headings, gitsigns word-diff, per-family fixups), re-applied on ColorScheme,
-- so a family switch always lands with the right set. Plugin specs stay pure
-- plugin declarations. Keep FAMILIES in sync with theme-mode's registry and
-- the ~/.config/tmux/<family>-<mode>.conf files.

local M = {}

local MODE_FILE = vim.env.HOME .. "/.cache/theme-mode"
local FAMILY_FILE = vim.env.HOME .. "/.cache/theme-family"
local DEFAULT_FAMILY = "doom-one"

-- alpha-blend two hex colours (a = share of c1).
local function blend(c1, c2, a)
  local out = {}
  for i = 2, 6, 2 do
    local v = tonumber(c1:sub(i, i + 1), 16) * a + tonumber(c2:sub(i, i + 1), 16) * (1 - a)
    out[#out + 1] = string.format("%02x", math.floor(v + 0.5))
  end
  return "#" .. table.concat(out)
end

local FAMILIES = {
  ["doom-one"] = {
    -- one scheme for both modes; it picks its palette from vim.o.background
    schemes = { dark = "doom-one", light = "doom-one" },
    accents = {
      dark = { heading1 = "#c678dd", heading = "#51afef" },
      light = { heading1 = "#a626a4", heading = "#4078f2" },
    },
    -- Fix two port defects (NTBBloodbath/doom-one.nvim; see plugins/doom-one.lua):
    -- comments are 2.3:1/2.7:1 unreadable (these are the emacs
    -- doom-one-brighter-comments values), and DiffAdd/Change/Delete are
    -- fg-only — no backgrounds — which starves codediff, native diff mode,
    -- and the word-diff glue below. Rebuild them as palette-blended washes.
    fixup = function(mode)
      local p = mode == "dark"
          and { bg = "#282c34", comment = "#5699af", green = "#98be65", red = "#ff6c6b", yellow = "#ecbe7b" }
        or { bg = "#fafafa", comment = "#3a888e", green = "#50a14f", red = "#e45649", yellow = "#986801" }
      local hl = vim.api.nvim_set_hl
      hl(0, "Comment", { fg = p.comment })
      hl(0, "CommentBold", { fg = p.comment, bold = true })
      hl(0, "DiffAdd", { bg = blend(p.green, p.bg, 0.22) })
      hl(0, "DiffDelete", { bg = blend(p.red, p.bg, 0.22) })
      hl(0, "DiffChange", { bg = blend(p.yellow, p.bg, 0.16) })
      hl(0, "DiffText", { bg = blend(p.yellow, p.bg, 0.38), bold = true })
    end,
  },
  github = {
    schemes = { dark = "github_dark_dimmed", light = "github_light" },
    accents = {
      dark = { heading1 = "#b083f0", heading = "#539bf5" },
      light = { heading1 = "#8250df", heading = "#0969da" },
    },
    -- stock palette needs no fixup
  },
  ["gruvbox-material"] = {
    -- one scheme for both modes; it picks its palette from vim.o.background
    schemes = { dark = "gruvbox-material", light = "gruvbox-material" },
    accents = {
      dark = { heading1 = "#d3869b", heading = "#7daea3" },
      light = { heading1 = "#945e80", heading = "#45707a" },
    },
    -- Comment floor: stock #928374 measures 4.0:1 dark / 3.0:1 light. Raise
    -- to palette grey2 (dark) / a floor-clearing dark grey (light): 5.3/5.2:1.
    fixup = function(mode)
      local c = mode == "dark" and "#a89984" or "#665c54"
      vim.api.nvim_set_hl(0, "Comment", { fg = c, italic = true })
    end,
  },
  zenbones = {
    -- one scheme for both modes; light is the paper-cream look
    schemes = { dark = "zenbones", light = "zenbones" },
    accents = {
      dark = { heading1 = "#b279a7", heading = "#6099c0" },
      light = { heading1 = "#88507d", heading = "#286486" },
    },
    -- Comment floor: stock #6e6763 is 3.1:1 dark / #948985 is 2.8:1 light.
    -- Dark warms up a step (5.1:1); light reuses the dark theme's own grey
    -- (4.8:1). Comments stay italic per the theme's design.
    fixup = function(mode)
      local c = mode == "dark" and "#928a85" or "#6e6763"
      vim.api.nvim_set_hl(0, "Comment", { fg = c, italic = true })
    end,
  },
  zenwritten = {
    -- zenbones' hue-stripped sibling (same plugin): pure grayscale body,
    -- same muted accent set. One scheme for both modes.
    schemes = { dark = "zenwritten", light = "zenwritten" },
    accents = {
      dark = { heading1 = "#b279a7", heading = "#6099c0" },
      light = { heading1 = "#88507d", heading = "#286486" },
    },
    -- Comment floor: stock #686868 is 3.1:1 dark / #8b8b8b is 3.0:1 light.
    fixup = function(mode)
      local c = mode == "dark" and "#8f8f8f" or "#696969"
      vim.api.nvim_set_hl(0, "Comment", { fg = c, italic = true })
    end,
  },
  kanso = {
    -- webhooked/kanso.nvim (kanagawa successor): mist dark, pearl light.
    -- Both variant colorschemes register colors_name = "kanso".
    schemes = { dark = "kanso-mist", light = "kanso-pearl" },
    colors_name = "kanso",
    accents = {
      dark = { heading1 = "#938aa9", heading = "#7fb4ca" },
      light = { heading1 = "#624c83", heading = "#4d699b" },
    },
    -- Comment floor: stock #75797f is 3.6:1 dark (lift to gray3, 5.3:1);
    -- pearl's #6d6d69 passes at 4.7:1. DiffDelete recolors deleted-line
    -- text red (kanagawa habit) — keep the theme's washes, drop the fg.
    fixup = function(mode)
      if mode == "dark" then
        vim.api.nvim_set_hl(0, "Comment", { fg = "#909398", italic = true })
        vim.api.nvim_set_hl(0, "DiffDelete", { bg = "#43242b" })
      else
        vim.api.nvim_set_hl(0, "DiffDelete", { bg = "#d9a594" })
      end
    end,
  },
  kanagawa = {
    -- rebelot/kanagawa.nvim: dragon (desaturated ink-wash, warm black) dark,
    -- lotus (yellow paper) light. All variants register colors_name "kanagawa".
    schemes = { dark = "kanagawa-dragon", light = "kanagawa-lotus" },
    colors_name = "kanagawa",
    accents = {
      dark = { heading1 = "#938aa9", heading = "#7fb4ca" },
      light = { heading1 = "#624c83", heading = "#4d699b" },
    },
    -- Dragon: comment dragonAsh #737c73 is 4.2:1 (floor 4.5) — lift to 5.2:1
    -- keeping its green cast. Lotus: body ink #545464 is only 6.2:1 on the
    -- yellow paper and comment #8a8980 is 2.9:1 — deepen both (8.1/5.1:1).
    -- Diff* stay stock: kanagawa ships proper bg-only washes in both modes.
    fixup = function(mode)
      if mode == "dark" then
        vim.api.nvim_set_hl(0, "Comment", { fg = "#848c84", italic = true })
      else
        vim.api.nvim_set_hl(0, "Normal", { fg = "#434350", bg = "#f2ecbc" })
        vim.api.nvim_set_hl(0, "Comment", { fg = "#63625b", italic = true })
      end
    end,
  },
  alabaster = {
    -- p00f/alabaster.nvim (tonsky's design): strict 4-hue budget — strings
    -- green, constants purple, definitions blue, comments red(light)/yellow
    -- (dark); everything else body fg. One scheme, branches on
    -- vim.o.background. Wired STOCK by request — no fixups. Known stock
    -- deviations from the eye spec: dark body 11.9:1 (band ceiling 10),
    -- light body #000 on #f7f7f7 = 19.6:1, light strings 3.9:1 (floor 4.5).
    schemes = { dark = "alabaster", light = "alabaster" },
    accents = {
      -- markview headings (switcher glue): reuse the theme's own
      -- definition-blue + constant-purple so no fifth hue enters.
      dark = { heading1 = "#cc8bc9", heading = "#71ade7" },
      light = { heading1 = "#7a3e9d", heading = "#325cc0" },
    },
  },
}

local applied ---@type string|nil  last family+mode we set, to skip redundant reloads

-- Read a state file's first line, trimmed; nil if missing.
local function read_state(path)
  local f = io.open(path, "r")
  if not f then
    return nil
  end
  local raw = f:read("l") or ""
  f:close()
  return (raw:gsub("%s+", ""))
end

local function normalize_mode(mode)
  return mode == "light" and "light" or "dark"
end

local function normalize_family(family)
  return FAMILIES[family] and family or DEFAULT_FAMILY
end

function M.read_state()
  return normalize_family(read_state(FAMILY_FILE)), normalize_mode(read_state(MODE_FILE))
end

-- markview heading colours (referenced by markview.lua's headings config).
local function set_headings(a)
  local hl = vim.api.nvim_set_hl
  hl(0, "MdHeading1", { fg = a.heading1, bold = true })
  for i = 2, 6 do
    hl(0, "MdHeading" .. i, { fg = a.heading, bold = true })
  end
  hl(0, "MdBullet", { fg = a.heading })
end

-- gitsigns word-diff readability (the `=` whole-file inline overlay, keymaps.lua).
-- gitsigns' inline word-diff groups (GitSigns{Change,Add,Delete}LnInline)
-- default to `reverse = true`, which paints dim token fgs (comments worst)
-- as unreadable blocks. Replace reverse with the theme's own diff
-- backgrounds + a forced bright Normal fg, so the emphasised word reads on
-- ANY underlying token. Reads the resolved palette at ColorScheme time, so
-- it is theme-agnostic and tracks every family/mode switch.
local function set_word_diff()
  local hl = vim.api.nvim_set_hl
  local function bg_of(name)
    return vim.api.nvim_get_hl(0, { name = name, link = false }).bg
  end
  local fg = vim.api.nvim_get_hl(0, { name = "Normal", link = false }).fg
  -- DiffText (word-emphasis) sits a shade lighter than DiffChange (the
  -- line bg), so the changed word still pops out of its own changed line.
  hl(0, "GitSignsChangeLnInline", { fg = fg, bg = bg_of("DiffText"), bold = true })
  hl(0, "GitSignsAddLnInline", { fg = fg, bg = bg_of("DiffAdd"), bold = true })
  hl(0, "GitSignsDeleteLnInline", { fg = fg, bg = bg_of("DiffDelete"), bold = true })
end

-- Runs on every ColorScheme. A manual :colorscheme (theme audition) won't
-- match the active family's scheme — skip its fixup/accents and apply only
-- the theme-agnostic word-diff glue, so auditions aren't painted over.
-- nvim-orgmode agenda readability (prefix n a / n t popups). The plugin
-- samples its @org.agenda.* colors from whatever the active theme defines,
-- which under minimal families (alabaster, zenwritten…) lands scheduled-item
-- text near-invisible. Pin them to semantic groups every family paints; the
-- plugin's own versions are `hi default`, so these explicit links win
-- regardless of load order.
local function set_org_agenda()
  local links = {
    ["@org.agenda.scheduled"] = "Normal",
    ["@org.agenda.scheduled_past"] = "WarningMsg",
    ["@org.agenda.deadline.upcoming"] = "WarningMsg",
    ["@org.agenda.deadline"] = "ErrorMsg",
  }
  for group, target in pairs(links) do
    vim.api.nvim_set_hl(0, group, { link = target })
  end
end

local function apply_overrides()
  local family, mode = M.read_state()
  local fam = FAMILIES[family]
  -- colors_name: guard override for themes whose variant colorschemes all
  -- register one shared name (e.g. kanso-mist sets colors_name = "kanso")
  if vim.g.colors_name == (fam.colors_name or fam.schemes[mode]) then
    if fam.fixup then
      fam.fixup(mode) -- before word-diff: it reads the Diff* bgs set here
    end
    set_headings(fam.accents[mode])
  end
  set_word_diff()
  set_org_agenda()
end

-- Apply family+mode by setting background and re-running :colorscheme. Skips
-- the reload if already active (a reload clears user highlights and re-runs
-- the theme build), unless `force` is set (used for the initial apply).
function M.apply(family, mode, force)
  family, mode = normalize_family(family), normalize_mode(mode)
  local key = family .. "/" .. mode
  if not force and key == applied then
    return
  end
  applied = key
  local fam = FAMILIES[family]
  if fam.pre then
    fam.pre(mode) -- variant globals the theme reads at :colorscheme time
  end
  vim.o.background = mode
  vim.cmd.colorscheme(fam.schemes[mode])
end

function M.apply_from_file(force)
  local family, mode = M.read_state()
  M.apply(family, mode, force)
end

local polls = {} -- libuv fs_poll handles, created lazily in start()

-- Apply the current state now and start watching both state files.
function M.start()
  -- Ensure the state files exist so fs_poll has targets.
  local defaults = { [MODE_FILE] = "dark", [FAMILY_FILE] = DEFAULT_FAMILY }
  for path, value in pairs(defaults) do
    if not vim.uv.fs_stat(path) then
      local f = io.open(path, "w")
      if f then
        f:write(value .. "\n")
        f:close()
      end
    end
  end

  vim.api.nvim_create_autocmd("ColorScheme", {
    group = vim.api.nvim_create_augroup("ThemeOverrides", { clear = true }),
    callback = apply_overrides,
  })

  M.apply_from_file(true)

  if next(polls) then
    return
  end
  for _, path in ipairs({ MODE_FILE, FAMILY_FILE }) do
    local poll = vim.uv.new_fs_poll()
    if poll then
      -- 1s cadence: imperceptible for a manual toggle, negligible overhead.
      poll:start(
        path,
        1000,
        vim.schedule_wrap(function()
          M.apply_from_file(false)
        end)
      )
      polls[#polls + 1] = poll
    end
  end
end

return M
