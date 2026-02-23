# Clawfox

CLI headless browser driven by Playwright. Commands start a long-lived daemon if needed; the daemon keeps one browser page and serves commands over a Unix socket.

## Setup

```bash
cd /path/to/clawfox
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/playwright install chromium
```

## Usage

Use the venv’s `clawfox` (or `python -m clawfox` with the venv active):

```bash
# Activate venv or use full path
clawfox/.venv/bin/clawfox go https://example.com
clawfox/.venv/bin/clawfox show --html
clawfox/.venv/bin/clawfox eval "document.title"
clawfox/.venv/bin/clawfox screenshot
clawfox/.venv/bin/clawfox click "role=button[name=\"Submit\"]"
clawfox/.venv/bin/clawfox select "input[name=email]"
clawfox/.venv/bin/clawfox fill "input[name=email]" "user@example.com"
clawfox/.venv/bin/clawfox type "input[name=password]" "secret"
clawfox/.venv/bin/clawfox wait "role=button[name='OK']"
clawfox/.venv/bin/clawfox url
clawfox/.venv/bin/clawfox stop
```

Selectors are [Playwright selectors](https://playwright.dev/python/docs/selectors) (e.g. `text=Submit`, `role=button[name="Save"]`, `#id`, CSS).

## Paths

- Socket/pid: `~/.clawfox/run/` (or `$CLAWFOX_HOME/run/`)
- Screenshots: `~/.clawfox/screenshots/` (timestamped filenames; daemon deletes files older than 1 day when taking a new screenshot)

## Design

See [docs/clawfox-design.md](docs/clawfox-design.md).
