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

-- Rebuild Diff{Add,Delete,Change,Text} as palette-blended background washes.
-- For themes that ship fg-only (or `reverse`) diffs, which starve codediff,
-- native diff mode, and the word-diff glue below. p = { bg, green, red, yellow }.
local function diff_washes(p)
  local hl = vim.api.nvim_set_hl
  hl(0, "DiffAdd", { bg = blend(p.green, p.bg, 0.22) })
  hl(0, "DiffDelete", { bg = blend(p.red, p.bg, 0.22) })
  hl(0, "DiffChange", { bg = blend(p.yellow, p.bg, 0.16) })
  hl(0, "DiffText", { bg = blend(p.yellow, p.bg, 0.38), bold = true })
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
    schemes = { dark = "github_dark_default", light = "github_light" },
    accents = {
      dark = { heading1 = "#d2a8ff", heading = "#58a6ff" },
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
  kanagawa = {
    -- rebelot/kanagawa.nvim: wave (the original — indigo night, saturated) dark,
    -- lotus (yellow paper) light. All variants register colors_name "kanagawa".
    schemes = { dark = "kanagawa-wave", light = "kanagawa-lotus" },
    colors_name = "kanagawa",
    accents = {
      dark = { heading1 = "#957fb8", heading = "#7fb4ca" }, -- oniViolet + springBlue
      light = { heading1 = "#624c83", heading = "#4d699b" },
    },
    -- Wave: comment fujiGray #727169 is 3.33:1 (floor 4.5) — lift toward
    -- fujiWhite, keeping the grey cast. Lotus: body ink #545464 is only 6.2:1
    -- on the yellow paper and comment #8a8980 is 2.9:1 — deepen both (8.1/5.1).
    -- Diff* stay stock: kanagawa ships proper bg-only washes in both modes.
    fixup = function(mode)
      if mode == "dark" then
        vim.api.nvim_set_hl(0, "Comment", { fg = blend("#dcd7ba", "#727169", 0.3), italic = true })
      else
        vim.api.nvim_set_hl(0, "Normal", { fg = "#434350", bg = "#f2ecbc" })
        vim.api.nvim_set_hl(0, "Comment", { fg = "#63625b", italic = true })
      end
    end,
  },
  solarized = {
    -- maxmx03/solarized.nvim, palette = "solarized" (Schoonover's original).
    -- Both palettes of this plugin register colors_name = "solarized" and load
    -- via the same :colorscheme, so `pre` selects which one gets built.
    schemes = { dark = "solarized", light = "solarized" },
    colors_name = "solarized",
    pre = function()
      require("solarized").setup({ palette = "solarized" }) -- variant stays "winter" (the canonical accents)
    end,
    accents = {
      dark = { heading1 = "#6c71c4", heading = "#268bd2" }, -- violet + blue
      light = { heading1 = "#6c71c4", heading = "#268bd2" },
    },
    -- Solarized is the hard case for the comment floor: its body fg is itself
    -- only 4.75:1 dark / 4.13:1 light, so a comment that clears 4.5:1 lands ON
    -- TOP of stock body. Fix by shifting one step up the theme's OWN base
    -- ladder (no new colours): body base0→base1 (5.6:1) and comment
    -- base01→base0 (4.8:1) dark. Light needs more room, so body deepens past
    -- base01 to 9.9:1 (the kanagawa-lotus precedent) and comment takes base01
    -- (5.0:1) — separation 4.9 vs 0.4 if body stayed put. Comments keep italic
    -- to carry the distinction the 0.86 dark separation can't alone.
    -- Diff* ship fg-only (DiffDelete/DiffText are `reverse`) — rebuild washes.
    fixup = function(mode)
      local hl = vim.api.nvim_set_hl
      local p = mode == "dark"
          and { bg = "#002b36", fg = "#93a1a1", comment = "#839496" }
        or { bg = "#fdf6e3", fg = "#0f4451", comment = "#586e75" }
      hl(0, "Normal", { fg = p.fg, bg = p.bg })
      hl(0, "Comment", { fg = p.comment, italic = true })
      diff_washes({
        bg = p.bg,
        green = "#859900",
        red = "#dc322f",
        yellow = "#b58900",
      })
    end,
  },
  ["rose-pine"] = {
    -- rose-pine/neovim: three variants (main/moon/dawn) as separate
    -- colorschemes that all register colors_name = "rose-pine".
    schemes = { dark = "rose-pine-main", light = "rose-pine-dawn" },
    colors_name = "rose-pine",
    accents = {
      dark = { heading1 = "#c4a7e7", heading = "#9ccfd8" }, -- iris + foam
      light = { heading1 = "#907aa9", heading = "#286983" }, -- iris + pine
    },
    -- Dawn's comment is `subtle` (#797593) at 4.02:1 — under the floor. The
    -- palette's next rung down is `text` (#575279, 6.66:1), which lands too
    -- close to body, so take the midpoint of the two: 5.12:1 against body's
    -- 8.69:1. Diff* ship real washes (add is teal, not green — rose-pine has
    -- no green) and are left alone.
    fixup = function(mode)
      if mode == "light" then
        vim.api.nvim_set_hl(0, "Comment", { fg = blend("#575279", "#797593", 0.5), italic = true })
      end
    end,
  },
  tokyonight = {
    -- folke/tokyonight.nvim: night (the darkest of the three darks — storm and
    -- moon sit on lighter, bluer bases) and day.
    -- Each variant registers its own colors_name, matching schemes[mode].
    schemes = { dark = "tokyonight-night", light = "tokyonight-day" },
    accents = {
      dark = { heading1 = "#bb9af7", heading = "#7aa2f7" }, -- purple + blue
      light = { heading1 = "#9854f1", heading = "#2e7de9" },
    },
    -- Worst comment contrast of any family here: night's #565f89 is 2.76:1 and
    -- day's #848cb5 is 2.54:1 (floor 4.5) — both are barely-there blues. Night
    -- lifts 40% toward body (5.06:1, against body's 10.59). Day is the harder
    -- one: its body fg is a BLUE (#3760bf) that only measures 4.52:1 itself, so
    -- a floor-clearing comment would land on top of body. Deepen body down the
    -- same blue ramp to 8.07:1 (the solarized-light precedent), which buys the
    -- comment room at 4.91:1.
    -- Diff* ship real bg-only washes in both modes and are left stock: night's
    -- add is a genuine BLUE (#243e4a, hue 198) rather than a green, which is
    -- what makes its diffs separate cleanly from the red delete.
    fixup = function(mode)
      local hl = vim.api.nvim_set_hl
      if mode == "dark" then
        hl(0, "Comment", { fg = blend("#c0caf5", "#565f89", 0.4), italic = true })
      else
        hl(0, "Normal", { fg = "#223c7d", bg = "#e1e2e7" })
        hl(0, "Comment", { fg = "#565e80", italic = true })
      end
    end,
  },
  catppuccin = {
    -- catppuccin/nvim: mocha (dark) / latte (light); frappe and macchiato are
    -- the mid-dark rungs we skip. Each variant registers its own colors_name.
    schemes = { dark = "catppuccin-mocha", light = "catppuccin-latte" },
    accents = {
      dark = { heading1 = "#cba6f7", heading = "#89b4fa" }, -- mauve + blue
      light = { heading1 = "#8839ef", heading = "#1e66f5" },
    },
    -- Mocha needs nothing: comments clear the floor stock (5.81:1) and its
    -- Diff* are real bg-only washes. Latte's comment (overlay1 #7c7f93) is
    -- 3.49:1 — the palette's next rung, subtext0, is still short at 4.37, so
    -- take the midpoint of subtext0/subtext1 (the rose-pine-dawn precedent):
    -- ~4.9:1 against body's 7.06:1.
    fixup = function(mode)
      if mode == "light" then
        vim.api.nvim_set_hl(0, "Comment", { fg = blend("#5c5f77", "#6c6f85", 0.5), italic = true })
      end
    end,
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
-- which under minimal families (zenwritten, zenbones…) lands scheduled-item
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
  -- register one shared name (e.g. rose-pine-dawn sets colors_name = "rose-pine")
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
