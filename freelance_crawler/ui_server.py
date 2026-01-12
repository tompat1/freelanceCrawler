from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from freelance_crawler.config import CrawlResult, CrawlerConfig
from freelance_crawler.crawler import run_crawl

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


@dataclass
class CrawlStatus:
    total_sites: int = 0
    completed_sites: int = 0
    current_site: str | None = None
    started_at: float | None = None
    finished_at: float | None = None
    results: list[CrawlResult] = field(default_factory=list)
    running: bool = False
    error: str | None = None


class StatusTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._status = CrawlStatus()

    def start(self) -> None:
        with self._lock:
            self._status = CrawlStatus(running=True, started_at=time.time())

    def update(self, completed: int, total: int, result: CrawlResult) -> None:
        with self._lock:
            self._status.completed_sites = completed
            self._status.total_sites = total
            self._status.current_site = result.site
            if len(self._status.results) < completed:
                self._status.results.append(result)
            else:
                self._status.results[completed - 1] = result

    def finish(self) -> None:
        with self._lock:
            self._status.running = False
            self._status.finished_at = time.time()
            self._status.current_site = None

    def set_error(self, message: str) -> None:
        with self._lock:
            self._status.error = message
            self._status.running = False
            self._status.finished_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            data = asdict(self._status)
            data["results"] = [asdict(result) for result in self._status.results]
            return data


STATUS_TRACKER = StatusTracker()


def build_config(payload: dict[str, Any] | None) -> CrawlerConfig:
    if not payload:
        return CrawlerConfig()
    return CrawlerConfig(
        directory_url=payload.get("directory_url", CrawlerConfig().directory_url),
        delay_s=float(payload.get("delay", CrawlerConfig().delay_s)),
        timeout_s=int(payload.get("timeout", CrawlerConfig().timeout_s)),
        output_csv=payload.get("output", CrawlerConfig().output_csv),
    )


def start_crawl(payload: dict[str, Any] | None) -> None:
    STATUS_TRACKER.start()
    config = build_config(payload)

    def run() -> None:
        try:
            results = run_crawl(config, STATUS_TRACKER.update)
            STATUS_TRACKER.finish()
            from freelance_crawler.crawler import write_csv

            write_csv(results, config.output_csv)
        except Exception as exc:  # pragma: no cover - best effort for UI
            STATUS_TRACKER.set_error(str(exc))

    thread = threading.Thread(target=run, daemon=True)
    thread.start()


class RequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path: Path) -> None:
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        data = path.read_bytes()
        content_type = "text/html"
        if path.suffix == ".css":
            content_type = "text/css"
        elif path.suffix == ".js":
            content_type = "text/javascript"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/status":
            self._send_json(STATUS_TRACKER.to_dict())
            return
        if self.path == "/":
            self._send_file(STATIC_DIR / "index.html")
            return
        if self.path.startswith("/static/"):
            asset = self.path.replace("/static/", "")
            self._send_file(STATIC_DIR / asset)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/start":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = None
        if length:
            payload = json.loads(self.rfile.read(length) or b"{}")
        if STATUS_TRACKER.to_dict().get("running"):
            self._send_json({"error": "Crawler already running"}, status=409)
            return
        start_crawl(payload)
        self._send_json({"status": "started"}, status=202)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8000), RequestHandler)
    print("UI running on http://localhost:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
