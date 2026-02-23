# Clawfox: CLI headless browser — design doc

**Status:** Draft  
**Purpose:** Let agents (and users) drive a headless browser from the CLI with a long-lived browser process.

---

## Overview

**clawfox** is a CLI that controls a headless browser (Playwright). The CLI starts a daemon process when needed so the browser stays up between commands. Commands navigate, extract content, run JS, click, type, and capture screenshots—all from the shell.

---

## Architecture

- **CLI:** Single entrypoint `clawfox`. Subcommands talk to a daemon over a socket (or similar). If the daemon is not running, the CLI starts it (e.g. in the background), then sends the command.
- **Daemon:** One process that:
  - Launches and owns a Playwright browser (e.g. Chromium) in headless mode.
  - Listens for commands (e.g. Unix socket or TCP localhost).
  - Executes one command at a time; queues or errors if a command is already in progress.
  - **Runs forever** once started—no auto-exit.
- **Playwright:** Used to drive the browser. One browser, one page (or one “current” page) per daemon unless we later add multi-tab support.

**Daemon lifecycle:**

- Any command (e.g. `clawfox go …`) checks for a running daemon (pidfile/socket); if missing, the CLI starts the daemon, waits until the socket is ready, then sends the command.
- The daemon stays running indefinitely so that repeated commands reuse the same browser/page. Only `clawfox stop` (or SIGTERM) shuts it down.

---

## Commands (proposed)

### Core

| Command | Description |
|--------|-------------|
| `clawfox go URL` | Navigate to URL. Wait for load event or timeout. Print page content (see Output format). |
| `clawfox show [--html]` | Same output as `go` (markdown with annotated links/elements, or `--html`) but for the **current** page—no navigation. Use after `go`, `click`, or when the page has changed. |
| `clawfox eval JS` | Evaluate JS in the current page context. Print the result (JSON-serialised or string). |
| `clawfox screenshot` | Take a screenshot of the current page. Write to a new file with a timestamp in the name (e.g. in a fixed dir like `~/.clawfox/screenshots/`). Print the file path. No path argument—agent never picks the path. |
| `clawfox click SELECTOR` | Click the element matching the Playwright selector. Optional: wait for navigation and then print content. |
| `clawfox select SELECTOR` | Resolve the selector and print what it matches (e.g. count, tag names, ids, visibility)—**no interaction**. For debugging when the agent is stuck (e.g. "why didn’t click work?"). |

### Input and waiting

| Command | Description |
|--------|-------------|
| `clawfox type SELECTOR TEXT` | Focus the element matching the Playwright selector and type TEXT (simulate keypresses). Useful for inputs and textareas. |
| `clawfox fill SELECTOR TEXT` | Set the value of the element (e.g. input/textarea) to TEXT (faster than type, no key events). |
| `clawfox wait SELECTOR [--timeout N]` | Block until an element matching the Playwright selector exists (and is visible, optional). Exit 0 when found, non-zero on timeout. |

### Navigation and state

| Command | Description |
|--------|-------------|
| `clawfox url` | Print the current page URL. |
| `clawfox back` | Browser back. Optionally wait and print content. |
| `clawfox forward` | Browser forward. Optionally wait and print content. |
| `clawfox reload` | Reload the current page. Wait for load then print content (or nothing). |

### Daemon and lifecycle

| Command | Description |
|--------|-------------|
| `clawfox daemon` | Start the daemon (blocking). Used internally or by the user for “keep browser open” sessions. |
| `clawfox stop` | Ask the daemon to shut down the browser and exit. |

---

## `clawfox go` and `clawfox show` — behaviour and output

- **`go` vs `show`:** `go` navigates then waits for load; `show` dumps the current page in the same format (no navigation).
- **Wait (go only):** Until “load” (or “domcontentloaded”) or a configurable timeout (e.g. 30s). Timeout → print whatever we have and exit non-zero or with a warning.
- **Output format (default):** Markdown derived from the page, with:
  - **Links annotated:** e.g. `[visible text](href)` or `[text](href "#id")` so the agent knows where links go.
  - **Interactive elements annotated:** Buttons and inputs include stable identifiers when present: `id`, `name`, or a suggested Playwright selector so the agent can use `clawfox click …` or `clawfox type …` in a follow-up.
- **`--html`:** Emit HTML (e.g. serialised document or outerHTML) instead of markdown for pipelines that need structure.

**Selectors:** All commands that take a selector (`click`, `type`, `fill`, `wait`, `select`) use **Playwright selectors**, not plain CSS. Playwright supports CSS, but also: `text=Submit`, `role=button[name="Save"]`, `test-id=login-form`, XPath, and chaining. When emitting an element map, prefer Playwright-style suggestions (e.g. `role=button`, `text=…`, or `#id`).
---

## Screenshots

- **Path:** The agent never chooses the path. Each screenshot is written to a new file with a timestamp in the filename (e.g. `~/.clawfox/screenshots/` or similar). CLI prints the path to stdout.
- **Cleanup:** No need to delete old screenshots while the daemon is not running. While the daemon *is* running, it may delete screenshot files in that directory that are older than one day (e.g. before writing a new one, or on a periodic check).

---

## Other possible commands (later)

- **Cookies / storage:** `clawfox cookies get|set|clear` for auth or session debugging.
- **Viewport / UA:** `clawfox viewport W H`, `clawfox user-agent STRING` to mimic devices.
- **Multiple tabs:** `clawfox tab list|new|switch N` if we grow to multi-tab.
- **Hover:** `clawfox hover SELECTOR` for dropdowns or tooltips before click/screenshot.

---

## Implementation notes

- **Language / stack:** Python or Node; Playwright has first-class support for both. Pick based on consistency with the rest of the stack (e.g. gary-robotman/cursor-claw are Python-heavy).
- **Socket vs stdio:** Unix socket (or TCP localhost) allows multiple CLI invocations to share one daemon. Stdio would require a single long-running `clawfox daemon` that reads line-based or JSON commands.
- **Markdown from HTML:** Use an HTML-to-Markdown converter (e.g. markdownify, turndown, or a simple custom pass) and a second pass to inject link hrefs and element annotations from the DOM.

---

## Open questions

1. **Timeout default for `go`:** 30s? Configurable via env or flag?
2. **Which load event:** `load` vs `domcontentloaded` — balance between “everything loaded” and speed.
3. **Single page vs tabs:** Start with one page; add tab support only if needed.
4. **Where clawfox lives:** Same repo as gary-robotman, or a separate repo (e.g. clawfox) that both gary-robotman and cursor-claw can depend on.

---

*Doc started 2025-02; to be updated as the design and implementation evolve.*
