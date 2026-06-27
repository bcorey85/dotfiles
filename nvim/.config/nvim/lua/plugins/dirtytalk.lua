-- vim-dirtytalk — programming spellcheck dictionary.
-- Supplements Vim's English word list with thousands of technical terms
-- (acronyms, brand names, git/docker/k8s/python/unix jargon, file extensions,
-- versions…) so markdown/comments stop turning red on jargon while real typos
-- still flag. Spell is enabled for markdown/text/gitcommit in autocmds.lua.
--
-- NOTE: the plugin's own :DirtytalkUpdate calls spellfile#WritableSpellDir(),
-- which doesn't exist in this Neovim (E117), so we compile the dict ourselves:
-- glob the bundled wordlists, concatenate, and mkspell into the writable site
-- spell dir (which is on the runtimepath, so spelllang finds programming.*.spl).
return {
  src = "psliwka/vim-dirtytalk",
  name = "vim-dirtytalk",
  setup = function()
    local spell_dir = vim.fn.stdpath("data") .. "/site/spell"

    local function have_dict()
      return vim.fn.filereadable(spell_dir .. "/programming.utf-8.spl") == 1
    end

    local function compile_dict()
      local lists = vim.fn.globpath(vim.o.runtimepath, "wordlists/*.words", false, true)
      if #lists == 0 then
        return false
      end
      local words = {}
      for _, file in ipairs(lists) do
        vim.list_extend(words, vim.fn.readfile(file))
      end
      local tmp = vim.fn.tempname()
      vim.fn.writefile(words, tmp)
      vim.fn.mkdir(spell_dir, "p")
      vim.cmd("mkspell! " .. vim.fn.fnameescape(spell_dir .. "/programming") .. " " .. vim.fn.fnameescape(tmp))
      return have_dict()
    end

    if not have_dict() then
      pcall(compile_dict)
    end

    -- Only add `programming` once the dict exists — otherwise Neovim's spell-file
    -- auto-downloader tries to fetch the (nonexistent) "programming" language
    -- and 404s. Genuine typos still flag via `en`.
    if have_dict() then
      vim.opt.spelllang = { "en", "programming" }
    else
      vim.opt.spelllang = { "en" }
      vim.notify("dirtytalk: could not build programming dict", vim.log.levels.WARN)
    end
  end,
}
