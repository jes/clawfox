"""CLI entry: clawfox <cmd> [args...]. Run with python -m clawfox."""
from __future__ import annotations

import argparse
import sys

from . import _client
from . import _daemon


HELP_EPILOG = """
Selectors (used by click, type, fill, wait, select):
  Use Playwright selector syntax, not just CSS. Examples:
    text=Submit              link or button with exact text "Submit"
    text="Log in"            quoted if text contains spaces
    role=button[name="OK"]   accessible role + name
    role=textbox             input or textarea
    #login-form              element id
    input[name=email]        CSS: input with name="email"
    [data-testid=submit]     attribute selector
  If a selector fails, use "clawfox select SELECTOR" to see what it matches (count, tags, visibility).

Typical workflow:
  clawfox go https://example.com     # open page, get markdown + interactive elements list
  clawfox click 'text=Sign in'       # click; output is new page content
  clawfox fill 'input[name=email]' my@email.com
  clawfox fill 'input[name=password]' mypassword
  clawfox click 'role=button[name="Log in"]'
  clawfox show                      # dump current page again without navigating
  clawfox screenshot               # take screenshot; prints path to PNG
  clawfox stop                     # shut down the daemon (otherwise it runs until you stop it)
"""


def main():
    parser = argparse.ArgumentParser(
        prog="clawfox",
        description="CLI headless browser (Playwright). Controls a long-lived browser in the background; "
        "the daemon starts automatically on first use. All commands use one shared page.",
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add_go():
        p = sub.add_parser(
            "go",
            help="Navigate to URL and print page content",
            description="Open URL, wait for load (or timeout), then print the page as markdown with "
            "annotated links and an 'Interactive elements' section listing suggested selectors for "
            "buttons/inputs. Use --html to get raw HTML instead.",
        )
        p.add_argument("url", help="URL to open (e.g. https://example.com)")
        p.add_argument("--html", action="store_true", help="Output HTML instead of markdown")
        p.add_argument("--timeout", type=int, default=30, help="Load timeout in seconds (default 30)")
        return p

    def add_show():
        p = sub.add_parser(
            "show",
            help="Print current page without navigating",
            description="Same output format as 'go' (markdown with links and interactive elements, or --html), "
            "but for the page already open. Use after 'go', 'click', 'back', etc. to re-dump the current state.",
        )
        p.add_argument("--html", action="store_true", help="Output HTML instead of markdown")
        return p

    def add_eval():
        p = sub.add_parser(
            "eval",
            help="Run JavaScript in the page and print the result",
            description="Evaluate a JavaScript expression in the page context. Result is JSON-encoded. "
            "Examples: document.title, document.querySelector('h1').textContent, window.location.href",
        )
        p.add_argument("js", help="JavaScript expression (e.g. document.title)")
        return p

    def add_screenshot():
        p = sub.add_parser(
            "screenshot",
            help="Take a screenshot and print its file path",
            description="Capture the current page to a new PNG file in ~/.clawfox/screenshots/ with a "
            "timestamp in the name. Prints the full path. No path argument; use the printed path to open or attach.",
        )
        return p

    def add_click():
        p = sub.add_parser(
            "click",
            help="Click an element by selector",
            description="Click the first element matching the Playwright selector. After the click, waits briefly "
            "for load and then prints the new page content (same format as 'go'). Use 'clawfox select SELECTOR' "
            "if the selector doesn't match what you expect.",
        )
        p.add_argument("selector", help="Playwright selector (e.g. role=button[name='Submit'], text=Next)")
        p.add_argument("--timeout", type=int, default=10, help="Wait up to this many seconds for element (default 10)")
        return p

    def add_select():
        p = sub.add_parser(
            "select",
            help="Show what a selector matches (no click/type)",
            description="Resolve the selector and print how many elements match and details (tag, id, name, "
            "visibility, text) for each (up to 20). Use this to debug why click/fill didn't work or to "
            "choose a better selector.",
        )
        p.add_argument("selector", help="Playwright selector to inspect")
        p.add_argument("--timeout", type=int, default=5, help="Wait up to this many seconds for element (default 5)")
        return p

    def add_type():
        p = sub.add_parser(
            "type",
            help="Type text into an input (simulates keypresses)",
            description="Focus the element and type the text character by character. Use for inputs that "
            "react to key events. For simple value setting, 'fill' is faster. Pass text as separate words; "
            "they are joined with spaces.",
        )
        p.add_argument("selector", help="Playwright selector (e.g. input[name=search], role=textbox)")
        p.add_argument("text", nargs="+", help="Text to type (multiple words joined with spaces)")
        p.add_argument("--timeout", type=int, default=10, help="Wait up to this many seconds for element (default 10)")
        return p

    def add_fill():
        p = sub.add_parser(
            "fill",
            help="Set the value of an input or textarea",
            description="Set the value of the element directly (no key events). Use for text fields, search boxes, "
            "etc. Pass value as separate words; they are joined with spaces.",
        )
        p.add_argument("selector", help="Playwright selector (e.g. input[name=email])")
        p.add_argument("text", nargs="+", help="Value to set (multiple words joined with spaces)")
        p.add_argument("--timeout", type=int, default=10, help="Wait up to this many seconds for element (default 10)")
        return p

    def add_wait():
        p = sub.add_parser(
            "wait",
            help="Wait until an element is visible",
            description="Block until an element matching the selector is visible, or timeout. Exit 0 on success, "
            "non-zero on timeout. Useful after navigation or click when the next element appears later.",
        )
        p.add_argument("selector", help="Playwright selector to wait for")
        p.add_argument("--timeout", type=int, default=30, help="Seconds to wait (default 30)")
        return p

    def add_url():
        p = sub.add_parser("url", help="Print the current page URL")
        p.description = "Print the URL of the page currently open in the browser."
        return p

    def add_back():
        p = sub.add_parser("back", help="Browser Back button")
        p.description = "Go back one page in history, then print the new page content (same format as 'go')."
        return p

    def add_forward():
        p = sub.add_parser("forward", help="Browser Forward button")
        p.description = "Go forward one page in history, then print the new page content."
        return p

    def add_reload():
        p = sub.add_parser("reload", help="Reload the current page")
        p.description = "Reload the page, wait for load, then print the new content."
        return p

    def add_daemon():
        p = sub.add_parser("daemon", help="Start the daemon (blocking)")
        p.description = "Start the browser daemon and accept commands. Usually you don't run this yourself; any other command will start the daemon automatically if it isn't running."
        return p

    def add_stop():
        p = sub.add_parser("stop", help="Stop the daemon")
        p.description = "Tell the daemon to shut down. The next clawfox command will start a fresh daemon."
        return p

    add_go()
    add_show()
    add_eval()
    add_screenshot()
    add_click()
    add_select()
    add_type()
    add_fill()
    add_wait()
    add_url()
    add_back()
    add_forward()
    add_reload()
    add_daemon()
    add_stop()

    args = parser.parse_args()

    if args.cmd == "daemon":
        _daemon.run_daemon()
        return

    # Build kwargs for send_command
    kwargs = {}
    if args.cmd == "go":
        kwargs["url"] = args.url
        kwargs["html"] = args.html
        kwargs["timeout_ms"] = args.timeout * 1000
    elif args.cmd == "show":
        kwargs["html"] = args.html
    elif args.cmd == "eval":
        kwargs["js"] = args.js
    elif args.cmd in ("click", "select", "type", "fill", "wait"):
        kwargs["selector"] = args.selector
        kwargs["timeout_ms"] = getattr(args, "timeout", 10) * 1000
        if args.cmd in ("type", "fill"):
            kwargs["text"] = " ".join(args.text) if isinstance(args.text, list) else args.text

    try:
        out = _client.send_command(args.cmd, **kwargs)
        if out:
            print(out, end="" if out.endswith("\n") else "\n")
    except RuntimeError as e:
        print(f"clawfox: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
