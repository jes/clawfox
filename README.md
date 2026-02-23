# Clawfox

CLI headless browser driven by Playwright. Commands start a long-lived daemon if needed; the daemon keeps one browser page and serves commands over a Unix socket.

## Setup

```bash
cd /path/to/clawfox
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/playwright install chromium
```

### Optional: add to PATH (.bashrc)

To run `clawfox` from any directory without the full path:

```bash
# Add to ~/.bashrc (adjust path to your clawfox clone)
export PATH="/path/to/clawfox/.venv/bin:$PATH"
```

Then you can run `clawfox go https://example.com` etc. from anywhere.

## Usage

Run `clawfox` (after adding the venv to PATH as above, or use `path/to/clawfox/.venv/bin/clawfox` or `python -m clawfox` with the venv active):

```bash
clawfox go https://example.com
clawfox show --html
clawfox eval "document.title"
clawfox screenshot
clawfox click "role=button[name=\"Submit\"]"
clawfox select "input[name=email]"
clawfox fill "input[name=email]" "user@example.com"
clawfox type "input[name=password]" "secret"
clawfox wait "role=button[name='OK']"
clawfox url
clawfox stop
```

Selectors are [Playwright selectors](https://playwright.dev/python/docs/selectors) (e.g. `text=Submit`, `role=button[name="Save"]`, `#id`, CSS).

## Paths

- Socket/pid: `~/.clawfox/run/` (or `$CLAWFOX_HOME/run/`)
- Screenshots: `~/.clawfox/screenshots/` (timestamped filenames; daemon deletes files older than 1 day when taking a new screenshot)

## Design

See [docs/clawfox-design.md](docs/clawfox-design.md).
