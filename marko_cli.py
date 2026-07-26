"""marko: a lightweight GFM + Mermaid markdown viewer for the terminal-to-browser pipeline."""
import argparse
import html
import os
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import markdown
from pygments.formatters import HtmlFormatter

STATE_DIR = Path(os.path.expanduser("~/.local/state/marko"))
WELCOME_MARKER = STATE_DIR / "welcomed"
SPARKLES = "✻✽✢✦✧"

PAGE_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
{css}
</style>
</head>
<body>
<article class="markdown-body">
{body}
</article>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<script>
mermaid.initialize({{
  startOnLoad: true,
  theme: window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'default'
}});
let lastMtime = null;
async function poll() {{
  try {{
    const res = await fetch('/mtime');
    const mtime = await res.text();
    if (lastMtime !== null && mtime !== lastMtime) location.reload();
    lastMtime = mtime;
  }} catch (e) {{}}
  setTimeout(poll, 1000);
}}
poll();
</script>
</body>
</html>
"""

BASE_CSS = """
:root { color-scheme: light dark; }
body {
  max-width: 860px; margin: 2rem auto; padding: 0 1.5rem;
  font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
  line-height: 1.6; background: #fff; color: #1f2328;
}
.markdown-body pre { padding: 1em; overflow: auto; border-radius: 6px; background: #f6f8fa; }
.markdown-body code { font-family: "SFMono-Regular", Consolas, monospace; }
.markdown-body :not(pre) > code { background: rgba(175,184,193,0.2); padding: .2em .4em; border-radius: 4px; }
.markdown-body table { border-collapse: collapse; }
.markdown-body th, .markdown-body td { border: 1px solid #d0d7de; padding: 6px 13px; }
.markdown-body blockquote { color: #59636e; border-left: .25em solid #d0d7de; padding: 0 1em; margin-left: 0; }
.markdown-body pre.mermaid { background: transparent; }
@media (prefers-color-scheme: dark) {
  body { background: #0d1117; color: #e6edf3; }
  .markdown-body pre { background: #161b22; }
  .markdown-body :not(pre) > code { background: rgba(110,118,129,0.4); }
  .markdown-body th, .markdown-body td, .markdown-body blockquote { border-color: #30363d; }
  .markdown-body blockquote { color: #9198a1; }
}
"""


def _mermaid_fence(source, language, css_class, options, md, **kwargs):
    return f'<pre class="mermaid">{html.escape(source)}</pre>'


def render(filepath):
    with open(filepath, encoding="utf-8") as f:
        text = f.read()

    md = markdown.Markdown(
        extensions=[
            "extra",  # tables, fenced_code, footnotes, attr_list, def_list
            "sane_lists",
            "pymdownx.tasklist",
            "pymdownx.tilde",  # strikethrough
            "pymdownx.superfences",
            "pymdownx.highlight",
        ],
        extension_configs={
            "pymdownx.tasklist": {"custom_checkbox": True},
            "pymdownx.superfences": {
                "custom_fences": [
                    {"name": "mermaid", "class": "mermaid", "format": _mermaid_fence}
                ]
            },
        },
    )
    body = md.convert(text)

    light_css = HtmlFormatter(style="default").get_style_defs(".codehilite")
    dark_css = HtmlFormatter(style="monokai").get_style_defs(".codehilite")
    css = (
        BASE_CSS
        + light_css
        + "\n@media (prefers-color-scheme: dark) {\n"
        + dark_css
        + "\n}\n"
    )

    return PAGE_TEMPLATE.format(
        title=html.escape(os.path.basename(filepath)), css=css, body=body
    )


def _spin(text, duration, done_text=None):
    """A short sparkle-spinner, in the vein of Claude Code's startup flourish."""
    if not sys.stdout.isatty():
        print(text)
        return
    end = time.time() + duration
    frame = 0
    sys.stdout.write("\033[?25l")  # hide cursor
    try:
        while time.time() < end:
            glyph = SPARKLES[frame % len(SPARKLES)]
            sys.stdout.write(f"\r\033[36m{glyph}\033[0m {text}\033[K")
            sys.stdout.flush()
            time.sleep(0.08)
            frame += 1
        sys.stdout.write(f"\r\033[32m✔\033[0m {done_text or text}\033[K\n")
    finally:
        sys.stdout.write("\033[?25h")  # show cursor
        sys.stdout.flush()


def welcome_animation():
    """One-time splash on first run — pip has no reliable post-install hook for
    console-script wheels, so first launch stands in for 'after installing'."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if WELCOME_MARKER.exists():
        return
    _spin("Welcome to Marko", duration=1.2)
    WELCOME_MARKER.touch()


def launch_animation(filename):
    _spin(f"Rendering {filename}", duration=0.5)


def make_handler(filepath):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/mtime":
                payload = str(os.path.getmtime(filepath)).encode()
                content_type = "text/plain"
            else:
                payload = render(filepath).encode("utf-8")
                content_type = "text/html; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass  # ponytail: silent by default, add --verbose to wire this to stderr if needed

    return Handler


def main():
    parser = argparse.ArgumentParser(
        prog="marko", description="Lightweight GFM + Mermaid markdown viewer"
    )
    parser.add_argument("file", help="Markdown file to view")
    parser.add_argument(
        "--port", type=int, default=0, help="Port to serve on (default: auto)"
    )
    parser.add_argument(
        "--no-open", action="store_true", help="Don't launch a browser automatically"
    )
    args = parser.parse_args()

    filepath = os.path.abspath(args.file)
    if not os.path.isfile(filepath):
        parser.error(f"no such file: {args.file}")

    welcome_animation()
    launch_animation(os.path.basename(filepath))

    server = HTTPServer(("127.0.0.1", args.port), make_handler(filepath))
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}/"
    print(f"marko: serving {args.file} at {url} (Ctrl+C to stop)")

    if not args.no_open:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nmarko: stopped")
        sys.exit(0)


if __name__ == "__main__":
    main()
