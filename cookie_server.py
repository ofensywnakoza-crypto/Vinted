"""
Lightweight HTTP server that receives the Vinted session cookie from the
Chrome extension and writes it to .cookie_sync.json.

Run standalone: python cookie_server.py
Or imported:    from cookie_server import start_cookie_server; start_cookie_server()
"""
import json
import os
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 27182
SYNC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cookie_sync.json")


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/cookie-sync":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            data = json.loads(body)
            cookie = data.get("cookie", "").strip()
            if not cookie:
                raise ValueError("empty cookie")
        except Exception as exc:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(f"Bad request: {exc}".encode())
            return

        record = {
            "cookie": cookie,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        with open(SYNC_PATH, "w") as f:
            json.dump(record, f, indent=2)

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, fmt, *args):  # silence default access log
        pass


def read_synced_cookie() -> dict | None:
    """Return {'cookie': str, 'updated_at': str} or None if file missing/invalid."""
    if not os.path.exists(SYNC_PATH):
        return None
    try:
        with open(SYNC_PATH) as f:
            data = json.load(f)
        if data.get("cookie"):
            return data
    except Exception:
        pass
    return None


def start_cookie_server(port: int = PORT) -> None:
    """Start the server in a daemon thread — call once from scheduler or app."""
    server = HTTPServer(("localhost", port), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[CookieServer] Nasłuchuje na http://localhost:{port}/cookie-sync", flush=True)


if __name__ == "__main__":
    print(f"Vinted Cookie Server — port {PORT}")
    print("Zatrzymaj: Ctrl+C")
    server = HTTPServer(("localhost", PORT), _Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSerwer zatrzymany.")
