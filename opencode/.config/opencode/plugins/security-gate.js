const CRED_FILE_PATTERN = /(\.aws\/(credentials|config)|\.kube\/config|\.docker\/config\.json|\.boto|\.s3cfg|\.netrc|\.git-credentials|\.npmrc|\.pypirc|\.gem\/credentials|vault\/password|1pass\.txt|github\.txt|\.(pem|key|p12|pfx)\b|\.ssh\/(id_(rsa|ed25519|ecdsa|dsa)|authorized_keys|config)|\.gnupg\/|\.config\/gcloud\/|\.azure\/(accessTokens|azureProfile|msal_token_cache)|\.config\/gh\/hosts\.yml|\.env(rc|(\.[a-z]+)*)?\b|(credentials|service[._]account|application_default_credentials)\.json|\.tfstate|\.vault-token|\.dev\.vars|\.htpasswd|token\.json)/i;

const CRED_ENV_PATTERN = /(ANTHROPIC_|AWS_SECRET|AWS_SESSION|GITHUB_TOKEN|GH_TOKEN|NPM_TOKEN|PYPI_TOKEN|DATABASE_URL|_SECRET|_PASSWORD|_KEY|_TOKEN|_CREDENTIAL)/;

const PROTECTED_WRITE_PATHS = /(\.zshrc|\.bashrc|\.bash_profile|\.zprofile|\.zshenv|\/\.ssh\/|\/\.aws\/|\/\.kube\/|\/\.docker\/config|\.gitconfig|\.git-credentials|\.github\/workflows|\.claude\/settings(\.local)?\.json|\/etc\/|Library\/LaunchAgents|\.env\b|\.git\/hooks\/)/;

const SHELL_HISTORY_PATTERN = /\.(bash_history|zsh_history|sh_history|python_history|node_repl_history|mysql_history|psql_history|irb_history|rediscli_history)$/i;

export const SecurityGate = async ({ project, client, $, directory, worktree }) => {
  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool === "bash") {
        const cmd = output.args.command || "";
        checkBashSafety(cmd);
      }

      if (input.tool === "read" || input.tool === "edit" || input.tool === "write") {
        const filePath = output.args.filePath || output.args.path || "";
        checkFileSafety(input.tool, filePath);
      }

      if (input.tool === "glob" || input.tool === "grep") {
        const path = output.args.path || "";
        if (path) checkReadSafety(path);
      }
    },
  };
};

function checkBashSafety(cmd) {
  if (!cmd) return;

  if (/\b(bash|sh|dash|zsh|ksh)\s+-(c|s)\b/i.test(cmd)) {
    throw new Error("[indirect_shell] Indirect shell execution (sh -c) is not allowed — prevents rule bypass");
  }

  if (/(^|\|\||&&|;|\s\|\s)\s*eval\s/i.test(cmd)) {
    throw new Error("[eval] eval is not allowed — prevents rule bypass via dynamic command construction");
  }

  if (/(^|\|\||&&|;|\|)\s*(\w+=[^\s$()`]*\s+)*exec\s/i.test(cmd)) {
    throw new Error("[exec_shell] exec replaces the current process and can bypass future hooks");
  }

  if (/(^|\|\||&&|;|\s\|\s)\s*source\s|(^|\|\||&&|;|\s\|\s)\s*\.\s+\S/i.test(cmd)) {
    if (!/\.(venv|virtualenv|env)\/bin\/activate|\/virtualenvs\/|nvm\.sh|\.cargo\/env/i.test(cmd)) {
      throw new Error("[source_dot] source/dot-source is not allowed — prevents rule bypass via external scripts");
    }
  }

  if (/\b(python3?|node|perl|ruby|php)\b.*(\s-(c|e|r)\b|\s--?(eval|command)\b)/i.test(cmd)) {
    const safeImports = /(import\s+(json|sys|os\.path|pathlib|re|math|hashlib|base64|urllib|collections|struct|platform|sysconfig|ast|tomllib?|configparser|csv|io|textwrap|shutil|tempfile|glob|fnmatch|copy|pprint|inspect|importlib|pkg_resources|packaging|setuptools|distutils)|JSON\.(parse|stringify)|require\(|console\.(log|error|warn|dir)|process\.(version|arch|platform|cwd)|Buffer\.(from|alloc))/;
    if (!safeImports.test(cmd)) {
      throw new Error("[interpreter_inline] Interpreter inline execution (python -c, node -e) is not allowed — prevents rule bypass");
    }
  }

  if (/\|\s*((\/usr(\/local)?\/s?bin\/)|\/s?bin\/)?(ba)?sh\b/i.test(cmd) ||
      /\|\s*((\/usr(\/local)?\/s?bin\/)|\/s?bin\/)?zsh\b/i.test(cmd) ||
      /\|\s*((\/usr(\/local)?\/s?bin\/)|\/s?bin\/)?dash\b/i.test(cmd) ||
      /\|\s*((\/usr(\/local)?\/s?bin\/)|\/s?bin\/)?ksh\b/i.test(cmd)) {
    throw new Error("[pipe_shell] Pipe-to-shell is not allowed — piping any command into a shell interpreter");
  }

  if (/curl\b.*(--output\b|-o\b)/i.test(cmd) && /\b(bash|sh|dash|zsh|ksh)\s+\S/i.test(cmd)) {
    throw new Error("[download_then_execute] Downloading a script then executing it bypasses pipe-to-shell protection");
  }

  if (/curl\b.*(-d\b|--data|--upload-file|-F\b|-T\b|--form)/i.test(cmd)) {
    if (!/https?:\/\/(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])(:[0-9]+)?(\/|$|\s)/i.test(cmd)) {
      throw new Error("[curl_upload] curl with data upload flags to external hosts may exfiltrate sensitive data");
    }
  }

  if (/wget\b.*--post-(data|file)/i.test(cmd)) {
    if (!/https?:\/\/(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])(:[0-9]+)?(\/|$|\s)/i.test(cmd)) {
      throw new Error("[wget_post] wget with POST flags to external hosts may exfiltrate sensitive data");
    }
  }

  if (/^\s*(env|printenv|set)\s*$/i.test(cmd)) {
    throw new Error("[env_dump] Dumping environment variables may expose secrets");
  }

  if (/(^|\|\||&&|;|\s\|\s)\s*(env|printenv)\s*\|/i.test(cmd)) {
    throw new Error("[env_dump_piped] Piped env/printenv commands may expose secrets");
  }

  if (/printenv\s+\S*(ANTHROPIC_|AWS_SECRET|AWS_SESSION|GITHUB_TOKEN|GH_TOKEN|NPM_TOKEN|PYPI_TOKEN|DATABASE_URL|_SECRET|_PASSWORD|_KEY|_TOKEN|_CREDENTIAL)/i.test(cmd)) {
    throw new Error("[printenv_sensitive] Reading sensitive environment variables may expose API keys and credentials");
  }

  if (/(cat|head|tail|less|more|sort|diff|jq|cut|strings|uniq|nl|tac|rev|od|xxd|hexdump|grep|rg|egrep|fgrep|awk|sed)\s+.*CRED_FILE_PATTERN/i.test(cmd) ||
      (/(cat|head|tail|less|more|sort|diff|jq|cut|strings|uniq|nl|tac|rev|od|xxd|hexdump|grep|rg|egrep|fgrep|awk|sed)\s+/i.test(cmd) && CRED_FILE_PATTERN.test(cmd))) {
    if (!/\.(example|sample|template|dist|defaults|schema|test)$/i.test(cmd)) {
      throw new Error("[cat_creds] Reading credential/secret files via shell is not allowed");
    }
  }

  if (/(cat|head|tail|less|more|sort|grep|rg|strings|diff)\s+.*SHELL_HISTORY_PATTERN/i.test(cmd) ||
      (/(cat|head|tail|less|more|sort|grep|rg|strings|diff)\s+/i.test(cmd) && SHELL_HISTORY_PATTERN.test(cmd))) {
    throw new Error("[shell_history_read] Reading shell history files is not allowed — may contain credentials");
  }

  if (/\b(grep|rg|ack|ag)\b.*(\s-[a-zA-Z]*[rRl]|--recursive|--files-with-matches).*(\bAKIA|sk-[a-zA-Z0-9]|PRIVATE KEY|password\s*[=:]|secret.?key\s*[=:]|api.?key\s*[=:]|access.?token\s*[=:]|auth.?token\s*[=:]|BEGIN RSA|BEGIN EC|BEGIN OPENSSH|BEGIN DSA|BEGIN PGP)/i.test(cmd)) {
    if (!/\b(src|frontend|backend|worker|app|lib|tests?|specs?|packages|services|components|node_modules|dist|build)\//i.test(cmd)) {
      throw new Error("[grep_cred_patterns] Searching for credential patterns across files is not allowed — potential credential harvesting");
    }
  }

  if (/\$\([^)]*\b(curl|wget|nc|ncat|socat|telnet|ssh|scp|rsync|fetch)\b/i.test(cmd)) {
    throw new Error("[cmd_sub_network_dollar] Network commands inside command substitution can exfiltrate data");
  }

  if (/`[^`]*\b(curl|wget|nc|ncat|socat|telnet|ssh|scp|rsync|fetch)\b/i.test(cmd)) {
    throw new Error("[cmd_sub_network_backtick] Network commands inside backtick command substitution can exfiltrate data");
  }

  if (/git\s+config\b.*\balias\./i.test(cmd)) {
    throw new Error("[git_config_alias] git aliases with ! prefix execute arbitrary shell commands — persistence vector");
  }

  if (/git\s+config\b.*\bcore\.hookspath\b\s+\S/i.test(cmd)) {
    throw new Error("[git_config_hooks_path] Redirecting git hooks path allows executing arbitrary scripts on git operations");
  }

  if (/ansible-vault\s+(view|decrypt)\b/i.test(cmd)) {
    throw new Error("[ansible_vault_view] ansible-vault view/decrypt is not allowed — use ansible-vault edit instead");
  }

  if (/(^|[^a-zA-Z0-9_-])(socat|telnet)($|[^a-zA-Z0-9_-])/i.test(cmd)) {
    throw new Error("[raw_network_tools] socat/telnet are not allowed");
  }

  if (/\bosascript\b/i.test(cmd)) {
    throw new Error("[osascript] osascript execution is not allowed — can control any application and execute arbitrary shell commands");
  }

  if (/\bsecurity\s+(find-generic-password|find-internet-password|dump-keychain)\b/i.test(cmd)) {
    throw new Error("[macos_keychain] Keychain credential extraction is not allowed");
  }

  if (/\bsecret-tool\s+lookup\b/i.test(cmd)) {
    throw new Error("[linux_secret_tool] Secret store credential extraction is not allowed");
  }

  if (/\bdd\b.*\bof=/i.test(cmd)) {
    throw new Error("[dd_write] dd can overwrite disk devices or files — not allowed");
  }

  if (/\b(mkfs(\.[a-z0-9]+)?|fdisk|gdisk|parted|diskutil\s+(eraseDisk|partitionDisk|eraseVolume))\b/i.test(cmd)) {
    throw new Error("[disk_format] Disk formatting and partitioning commands are not allowed");
  }

  if (/\bxargs\b/i.test(cmd)) {
    if (!/\bxargs\s+(-[a-zA-Z0-9]+\s+|-I\s*\S+\s+)*(grep|rg|ack|ag|wc|ls|stat|file|head|tail|basename|dirname|echo)\b/i.test(cmd)) {
      throw new Error("[xargs_exec] xargs executes commands from stdin — bypasses keyword-based rules");
    }
  }

  if (/\bfind\b.*-delete\b/i.test(cmd)) {
    if (!/(^|\/|\s)\.cache(\/[a-zA-Z0-9_-][^\/\s]*)*\/?(\s|$)|node_modules|\/tmp\/|\.pytest_cache|\.mypy_cache|\.ruff_cache|\.DS_Store/i.test(cmd)) {
      throw new Error("[find_delete] find -delete removes matched files unconditionally — high blast-radius destructive operation");
    }
  }

  if (/\bfind\b.*-(exec|execdir)\b/i.test(cmd)) {
    if (!/\b(exec|execdir)\s+(\/usr\/bin\/|\/bin\/)?(wc|grep|rg|ack|ag|cat|head|tail|ls|stat|file|basename|dirname|echo)\s/i.test(cmd)) {
      throw new Error("[find_exec] find -exec/-execdir executes commands on matched files — bypasses keyword-based rules");
    }
  }

  if (/\bawk\b.*\b(system\s*\(|getline)/i.test(cmd)) {
    throw new Error("[awk_system] awk system()/getline executes arbitrary commands — bypasses keyword-based rules");
  }

  if (/\bsed\b.*(\/e\b|[0-9$,]+e\b)/i.test(cmd)) {
    throw new Error("[sed_execute] sed e-flag executes the pattern space as a shell command — bypasses keyword-based rules");
  }

  if (/(bash|sh|zsh|ksh)\s+<<<|\|\s*(bash|sh|zsh|ksh)\s+<</i.test(cmd)) {
    throw new Error("[here_string_shell] Here-strings and here-docs fed to a shell interpreter execute arbitrary code");
  }

  if (/(cat|head|tail|less|more|strings|xxd|od|tac|hexdump)\s+\/proc\/(self|\$\$|[0-9]+)\/environ/i.test(cmd)) {
    throw new Error("[proc_environ] Reading /proc/self/environ exposes all environment variables");
  }

  if (/(^|[^a-zA-Z0-9_-])(nc|ncat)($|[^a-zA-Z0-9_-])/i.test(cmd)) {
    if (!/\bnc(at)?\s+[^|;&]*-\w*z\w*\b/i.test(cmd)) {
      throw new Error("[raw_network_tools_nc] Raw netcat is not allowed — use nc -z for port probes");
    }
  }
}

function checkFileSafety(tool, filePath) {
  if (!filePath) return;

  const resolved = filePath.replace(/^~/, process.env.HOME || "");
  const expanded = resolved.replace(/\.\.+/g, ".");

  if (tool === "read") {
    checkReadSafety(expanded);
  }

  if (tool === "edit" || tool === "write") {
    checkWriteSafety(expanded);
  }
}

function checkReadSafety(filePath) {
  if (!filePath) return;

  if (CRED_FILE_PATTERN.test(filePath) && !/\.(example|sample|template|dist|defaults|schema|test)$/i.test(filePath)) {
    throw new Error(`[read_creds] Reading credential/secret files is not allowed: ${filePath}`);
  }

  if (SHELL_HISTORY_PATTERN.test(filePath)) {
    throw new Error(`[shell_history] Reading shell history files is not allowed: ${filePath}`);
  }

  if (/\/proc\/(self|\$\$|[0-9]+)\/environ/i.test(filePath)) {
    throw new Error("[proc_environ] Reading /proc/self/environ exposes all environment variables");
  }

  if (/(Chrome|Chromium|Google\/Chrome)\/(Default|Profile\s*\d+)\/(Login Data|Cookies|Web Data)/i.test(filePath)) {
    throw new Error("[chrome_creds] Reading browser credential stores is not allowed");
  }

  if (/\.mozilla\/firefox\/[^\/]+\/(logins\.json|cookies\.sqlite|key[34]\.db|cert9\.db)/i.test(filePath)) {
    throw new Error("[firefox_creds] Reading browser credential stores is not allowed");
  }

  if (/Library\/Cookies\/Cookies\.binarycookies/i.test(filePath)) {
    throw new Error("[safari_cookies] Reading browser credential stores is not allowed");
  }

  if (/(^|\/)[^/]*decrypted[^/]*\.(ya?ml|json|env|txt|key|pem|gpg|enc)$/i.test(filePath) || /[^/]+\.decrypted$/i.test(filePath)) {
    throw new Error("[decrypted_files] Reading decrypted secret/vault files is not allowed");
  }
}

function checkWriteSafety(filePath) {
  if (!filePath) return;

  if (PROTECTED_WRITE_PATHS.test(filePath) && !/\.(example|sample|template|dist|defaults|schema|test)$/i.test(filePath)) {
    throw new Error(`[write_protected] Writing to protected paths is not allowed: ${filePath}`);
  }
}
