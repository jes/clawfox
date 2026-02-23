"""Daemon: one Playwright browser, Unix socket server, one command at a time."""
from __future__ import annotations

import json
import os
import signal
import socket
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from ._content import INTERACTIVE_ELEMENTS_JS, build_go_output
from ._paths import (
    DEFAULT_GO_TIMEOUT_MS,
    PIDFILE_PATH,
    RUN_DIR,
    SCREENSHOT_DIR,
    SCREENSHOT_MAX_AGE_SECONDS,
    SOCKET_PATH,
)

def _chrome_version_headers(browser):
    """Build UA and sec-ch-ua from the actual Chromium version (not hardcoded)."""
    try:
        full = getattr(browser, "version", None) or "131.0.0.0"
    except Exception:
        full = "131.0.0.0"
    major = full.split(".")[0]
    user_agent = (
        f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{full} Safari/537.36"
    )
    extra_headers = {
        "sec-ch-ua": f'"Chromium";v="{major}", "Google Chrome";v="{major}", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Linux"',
    }
    return user_agent, extra_headers, major


def _write_pid():
    os.makedirs(RUN_DIR, mode=0o700, exist_ok=True)
    with open(PIDFILE_PATH, "w") as f:
        f.write(str(os.getpid()))


def _delete_pid():
    try:
        os.unlink(PIDFILE_PATH)
    except OSError:
        pass


def _screenshot_cleanup():
    """Remove screenshot files older than SCREENSHOT_MAX_AGE_SECONDS."""
    try:
        p = Path(SCREENSHOT_DIR)
        if not p.exists():
            return
        cutoff = time.time() - SCREENSHOT_MAX_AGE_SECONDS
        for f in p.iterdir():
            if f.is_file() and f.stat().st_mtime < cutoff:
                try:
                    f.unlink()
                except OSError:
                    pass
    except OSError:
        pass


def _run_cmd(page, cmd: str, **kwargs) -> dict:
    """Execute one command; returns {ok: bool, output?: str, error?: str}."""
    try:
        if cmd == "go":
            url = kwargs.get("url", "")
            timeout = int(kwargs.get("timeout_ms", DEFAULT_GO_TIMEOUT_MS))
            as_html = kwargs.get("html", False)
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            html = page.content()
            elements = page.evaluate(INTERACTIVE_ELEMENTS_JS)
            out = build_go_output(html, elements, as_html=as_html)
            return {"ok": True, "output": out}

        if cmd == "show":
            as_html = kwargs.get("html", False)
            html = page.content()
            elements = page.evaluate(INTERACTIVE_ELEMENTS_JS)
            out = build_go_output(html, elements, as_html=as_html)
            return {"ok": True, "output": out}

        if cmd == "eval":
            js = kwargs.get("js", "")
            result = page.evaluate(f"() => {{ return ({js}); }}")
            # Serialise for JSON (Playwright returns JSON-serialisable values)
            return {"ok": True, "output": json.dumps(result, default=str)}

        if cmd == "screenshot":
            os.makedirs(SCREENSHOT_DIR, mode=0o700, exist_ok=True)
            _screenshot_cleanup()
            name = f"screenshot_{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}.png"
            path = os.path.join(SCREENSHOT_DIR, name)
            page.screenshot(path=path)
            return {"ok": True, "output": path}

        if cmd == "click":
            selector = kwargs.get("selector", "")
            timeout = int(kwargs.get("timeout_ms", 10_000))
            page.click(selector, timeout=timeout)
            # Optional: wait for navigation and return new content
            try:
                page.wait_for_load_state("domcontentloaded", timeout=2000)
            except Exception:
                pass
            html = page.content()
            elements = page.evaluate(INTERACTIVE_ELEMENTS_JS)
            out = build_go_output(html, elements, as_html=False)
            return {"ok": True, "output": out}

        if cmd == "select":
            selector = kwargs.get("selector", "")
            timeout = int(kwargs.get("timeout_ms", 5_000))
            loc = page.locator(selector)
            count = loc.count()
            lines = [f"count: {count}"]
            for i in range(min(count, 20)):
                try:
                    el = loc.nth(i)
                    info = el.evaluate(
                        """el => ({
                        tag: el.tagName.toLowerCase(),
                        id: el.id || null,
                        name: el.name || null,
                        visible: el.offsetParent !== null && (el.offsetWidth > 0 || el.offsetHeight > 0),
                        text: (el.textContent || '').trim().slice(0, 60)
                    })"""
                    )
                    lines.append(f"  [{i}] {info}")
                except Exception as e:
                    lines.append(f"  [{i}] error: {e}")
            return {"ok": True, "output": "\n".join(lines)}

        if cmd == "type":
            selector = kwargs.get("selector", "")
            text = kwargs.get("text", "")
            timeout = int(kwargs.get("timeout_ms", 10_000))
            page.locator(selector).first.click(timeout=timeout)
            page.keyboard.type(text, delay=0)
            return {"ok": True, "output": "ok"}

        if cmd == "fill":
            selector = kwargs.get("selector", "")
            text = kwargs.get("text", "")
            timeout = int(kwargs.get("timeout_ms", 10_000))
            page.fill(selector, text, timeout=timeout)
            return {"ok": True, "output": "ok"}

        if cmd == "wait":
            selector = kwargs.get("selector", "")
            timeout = int(kwargs.get("timeout_ms", 30_000))
            page.wait_for_selector(selector, state="visible", timeout=timeout)
            return {"ok": True, "output": "ok"}

        if cmd == "url":
            return {"ok": True, "output": page.url}

        if cmd == "back":
            page.go_back(wait_until="domcontentloaded")
            html = page.content()
            elements = page.evaluate(INTERACTIVE_ELEMENTS_JS)
            return {"ok": True, "output": build_go_output(html, elements, as_html=False)}

        if cmd == "forward":
            page.go_forward(wait_until="domcontentloaded")
            html = page.content()
            elements = page.evaluate(INTERACTIVE_ELEMENTS_JS)
            return {"ok": True, "output": build_go_output(html, elements, as_html=False)}

        if cmd == "reload":
            page.reload(wait_until="domcontentloaded")
            html = page.content()
            elements = page.evaluate(INTERACTIVE_ELEMENTS_JS)
            return {"ok": True, "output": build_go_output(html, elements, as_html=False)}

        if cmd == "stop":
            return {"ok": True, "output": "stopping", "stop": True}

        return {"ok": False, "error": f"unknown command: {cmd}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def run_daemon():
    """Run the browser and socket server until stop or SIGTERM."""
    _write_pid()
    stop_requested = [False]  # ref so handler can set it

    def on_signal(_signum, _frame):
        stop_requested[0] = True

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    if os.path.exists(SOCKET_PATH):
        try:
            os.unlink(SOCKET_PATH)
        except OSError:
            pass
    os.makedirs(RUN_DIR, mode=0o700, exist_ok=True)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(SOCKET_PATH)
    sock.listen(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        user_agent, extra_headers, chrome_major = _chrome_version_headers(browser)
        context = browser.new_context(
            user_agent=user_agent,
            extra_http_headers=extra_headers,
        )
        # Make navigator.userAgentData look like desktop Chrome (reduces "headless" detection)
        try:
            context.add_init_script(
                f"""
                try {{
                    Object.defineProperty(navigator, 'userAgentData', {{
                        get: () => ({{
                            brands: [
                                {{ brand: 'Chromium', version: '{chrome_major}' }},
                                {{ brand: 'Google Chrome', version: '{chrome_major}' }},
                                {{ brand: 'Not_A Brand', version: '24' }}
                            ],
                            mobile: false,
                            platform: 'Linux'
                        }}),
                        configurable: true
                    }});
                }} catch (e) {{}}
                """
            )
        except Exception:
            pass
        page = context.new_page()

        try:
            while not stop_requested[0]:
                sock.settimeout(1.0)
                try:
                    conn, _ = sock.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                try:
                    buf = b""
                    while b"\n" not in buf and len(buf) < 1_000_000:
                        chunk = conn.recv(4096)
                        if not chunk:
                            break
                        buf += chunk
                    line = buf.decode("utf-8", errors="replace").split("\n", 1)[0]
                    req = json.loads(line)
                    cmd = req.get("cmd", "")
                    args = req.get("args", req)
                    result = _run_cmd(page, cmd, **args)
                    if result.get("stop"):
                        stop_requested[0] = True
                    conn.send((json.dumps(result) + "\n").encode("utf-8"))
                except Exception as e:
                    try:
                        conn.send((json.dumps({"ok": False, "error": str(e)}) + "\n").encode("utf-8"))
                    except Exception:
                        pass
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass

        finally:
            browser.close()

    try:
        sock.close()
    except Exception:
        pass
    try:
        os.unlink(SOCKET_PATH)
    except OSError:
        pass
    _delete_pid()
