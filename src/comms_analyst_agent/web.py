from __future__ import annotations

import argparse
import base64
import binascii
import dataclasses
import html
import hmac
import json
import os
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .pipeline import run_pipeline
from .prompt_parser import parse_prompt


def _collect_reports(output_root: Path, limit: int = 20) -> list[Path]:
    reports = list(output_root.glob("*/*/report.md"))
    reports.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return reports[:limit]


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _is_authorized(auth_header: str | None, username: str, password: str) -> bool:
    if not auth_header or not auth_header.startswith("Basic "):
        return False
    token = auth_header.split(" ", 1)[1].strip()
    try:
        decoded = base64.b64decode(token).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return False
    if ":" not in decoded:
        return False
    given_user, given_password = decoded.split(":", 1)
    return hmac.compare_digest(given_user, username) and hmac.compare_digest(given_password, password)


def _render_dashboard(output_root: Path, message: str = "", error: str = "") -> str:
    reports = _collect_reports(output_root)
    cards: list[str] = []
    for report in reports:
        run_dir = report.parent
        rel = run_dir.relative_to(output_root)
        target, run_id = rel.parts[0], rel.parts[1]
        cards.append(
            f"""
            <div class="card">
              <div class="card-title">{html.escape(target)}</div>
              <div class="card-meta">{html.escape(run_id)}</div>
              <div class="card-actions">
                <a href="/view?kind=md&run={html.escape(str(rel))}">Open report</a>
                <a href="/view?kind=json&run={html.escape(str(rel))}">View JSON</a>
              </div>
            </div>
            """
        )

    card_html = "\n".join(cards) if cards else '<p class="empty">No reports yet. Run a prompt above.</p>'
    message_html = f'<div class="notice ok">{html.escape(message)}</div>' if message else ""
    error_html = f'<div class="notice err">{html.escape(error)}</div>' if error else ""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Comms Analyst Dashboard</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; background: #f7f8fb; color: #111827; }}
    .wrap {{ max-width: 920px; margin: 0 auto; padding: 24px; }}
    h1 {{ margin: 0 0 12px; font-size: 1.6rem; }}
    .panel {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 16px; margin-bottom: 16px; }}
    .prompt {{ width: 100%; box-sizing: border-box; min-height: 92px; padding: 10px; border: 1px solid #d1d5db; border-radius: 8px; }}
    .row {{ display: flex; gap: 10px; margin-top: 10px; flex-wrap: wrap; }}
    button {{ background: #111827; color: #fff; border: 0; border-radius: 8px; padding: 10px 14px; cursor: pointer; }}
    .hint {{ color: #4b5563; font-size: .92rem; margin-top: 6px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }}
    .card {{ border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; background: #fff; }}
    .card-title {{ font-weight: 600; }}
    .card-meta {{ color: #6b7280; font-size: .88rem; margin: 4px 0 8px; }}
    .card-actions a {{ margin-right: 10px; font-size: .9rem; }}
    .notice {{ padding: 10px; border-radius: 8px; margin-bottom: 12px; }}
    .ok {{ background: #ecfdf5; border: 1px solid #a7f3d0; }}
    .err {{ background: #fef2f2; border: 1px solid #fecaca; }}
    .empty {{ color: #6b7280; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Comms Analyst Dashboard</h1>
    {message_html}
    {error_html}
    <div class="panel">
      <form method="post" action="/run">
        <label for="prompt"><strong>What should we monitor?</strong></label>
        <textarea class="prompt" id="prompt" name="prompt" required placeholder='Example: Track sentiment around "GitHub Copilot" over the last 48 hours, competitors: OpenAI, GitLab'></textarea>
        <div class="row"><button type="submit">Run report</button></div>
      </form>
      <div class="hint">Type plain English prompts. Reports appear below when complete.</div>
    </div>
    <div class="panel">
      <strong>Recent reports</strong>
      <div class="grid" style="margin-top:10px;">{card_html}</div>
    </div>
  </div>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    output_root = Path("outputs")
    auth_username: str | None = None
    auth_password: str | None = None

    def _read_form(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(length).decode("utf-8")
        parsed = parse_qs(payload)
        return {k: v[0] for k, v in parsed.items() if v}

    def _respond_html(self, page: str, status: int = HTTPStatus.OK) -> None:
        body = page.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth_required(self) -> bool:
        return bool(self.auth_username and self.auth_password)

    def _enforce_auth(self) -> bool:
        if not self._auth_required():
            return True
        header = self.headers.get("Authorization")
        if _is_authorized(header, self.auth_username or "", self.auth_password or ""):
            return True
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("WWW-Authenticate", 'Basic realm="Comms Analyst Dashboard"')
        self.send_header("Content-Length", "0")
        self.end_headers()
        return False

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            body = b"ok"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if not self._enforce_auth():
            return

        if parsed.path == "/":
            params = parse_qs(parsed.query)
            page = _render_dashboard(
                self.output_root,
                message=params.get("message", [""])[0],
                error=params.get("error", [""])[0],
            )
            self._respond_html(page)
            return

        if parsed.path == "/view":
            params = parse_qs(parsed.query)
            kind = params.get("kind", ["md"])[0]
            run = params.get("run", [""])[0]
            run_dir = (self.output_root / run).resolve()
            if not _is_within(run_dir, self.output_root):
                self._respond_html("<h3>Invalid report path.</h3>", status=HTTPStatus.BAD_REQUEST)
                return
            file_path = run_dir / ("report.json" if kind == "json" else "report.md")
            if not file_path.exists():
                self._respond_html("<h3>Report not found.</h3>", status=HTTPStatus.NOT_FOUND)
                return

            text = file_path.read_text(encoding="utf-8")
            content = html.escape(text)
            title = "JSON Report" if kind == "json" else "Markdown Report"
            self._respond_html(
                f"""<!doctype html><html><body style="font-family: system-ui; margin: 20px;">
                <p><a href="/">← Back to dashboard</a></p>
                <h2>{title}</h2>
                <pre style="white-space: pre-wrap; word-wrap: break-word; border: 1px solid #ddd; padding: 12px; border-radius: 8px;">{content}</pre>
                </body></html>"""
            )
            return

        self._respond_html("<h3>Not found.</h3>", status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if not self._enforce_auth():
            return
        if parsed.path != "/run":
            self._respond_html("<h3>Not found.</h3>", status=HTTPStatus.NOT_FOUND)
            return

        form = self._read_form()
        prompt = form.get("prompt", "").strip()
        if not prompt:
            page = _render_dashboard(self.output_root, error="Please enter a prompt.")
            self._respond_html(page, status=HTTPStatus.BAD_REQUEST)
            return

        try:
            config = parse_prompt(prompt)
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp:
                json.dump(dataclasses.asdict(config), tmp, indent=2)
                config_path = tmp.name
            try:
                output_path = run_pipeline(config_path=config_path, output_root=str(self.output_root))
            finally:
                os.unlink(config_path)
            rel = output_path.resolve().relative_to(self.output_root.resolve())
            message = f"Report complete: {rel}"
            page = _render_dashboard(self.output_root, message=message)
            self._respond_html(page)
        except Exception as exc:
            page = _render_dashboard(self.output_root, error=f"Failed to generate report: {exc}")
            self._respond_html(page, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the minimal Comms Analyst web dashboard.")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"), help="Host bind address (default: HOST env or 127.0.0.1)")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8080")), help="Port (default: PORT env or 8080)")
    parser.add_argument("--output-dir", default=os.getenv("OUTPUT_DIR", "outputs"), help="Output directory (default: OUTPUT_DIR env or outputs)")
    parser.add_argument("--require-auth", action="store_true", help="Require HTTP Basic Auth using COMMS_DASHBOARD_USERNAME and COMMS_DASHBOARD_PASSWORD.")
    args = parser.parse_args()

    auth_username = os.getenv("COMMS_DASHBOARD_USERNAME")
    auth_password = os.getenv("COMMS_DASHBOARD_PASSWORD")
    if args.require_auth and not (auth_username and auth_password):
        raise SystemExit("Missing COMMS_DASHBOARD_USERNAME/COMMS_DASHBOARD_PASSWORD for --require-auth.")

    DashboardHandler.output_root = Path(args.output_dir)
    DashboardHandler.auth_username = auth_username
    DashboardHandler.auth_password = auth_password
    DashboardHandler.output_root.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Dashboard running at http://{args.host}:{args.port}")
    if DashboardHandler.auth_username and DashboardHandler.auth_password:
        print("Authentication: enabled (HTTP Basic Auth)")
    else:
        print("Authentication: disabled")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down dashboard.")
        server.server_close()


if __name__ == "__main__":
    main()
