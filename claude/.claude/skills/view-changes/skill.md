# View Changes

Launch the dev server (if not running) and open a Playwright browser to visually review the current work.

## Usage

```
/view-changes [path]
```

- **With a path:** Navigate directly to that route (e.g., `/view-changes /layout/page-toolbar`)
- **Without a path:** Auto-detect the most relevant demo page from recent git changes

## Instructions

1. **Detect the dev server port:**
   ```bash
   # Find a running Vite/Next/etc dev server
   lsof -ti:5173 -ti:5174 -ti:5175 -ti:5176 -ti:5177 -ti:5178 -ti:5179 -ti:5180 -ti:5181 -ti:5182 -ti:5183 -ti:5184 -ti:5185 -ti:5186 -ti:5187 -ti:5188 -ti:5189 -ti:5190 -ti:3000 -ti:3001 -ti:8080 2>/dev/null | head -1
   ```
   If no server is running, start one with `npm run dev` (or the project's dev command from `package.json`) in the background, then wait for it to be ready.

2. **Determine the URL path:**
   - If a path argument was provided, use it directly.
   - If no path was provided, check `git diff --name-only HEAD` for recently changed demo/page files (e.g., `src/pages/*Page.vue`), then look up the corresponding route in the router file.

3. **Navigate with Playwright MCP:**
   Use the `browser_navigate` tool to open `http://localhost:{port}{path}`.

4. **Take a snapshot:**
   Use `browser_snapshot` so the user can see the current state and interact further if needed.

5. **Let the user review:**
   Tell the user the page is open and they can ask for interactions, screenshots, or navigation to other demo sections.
