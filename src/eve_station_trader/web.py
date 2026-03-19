from __future__ import annotations

import argparse
import json
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .config import (
    BROKER_FEE_DEFAULT,
    DEFAULT_CACHE_TTL_SECONDS,
    SALES_TAX_DEFAULT,
    TOP_RESULTS_DEFAULT,
)
from .ingestion import IngestionService
from .jobs import IngestionJobManager, serialize_job
from .service import TraderService


STATIC_DIR = Path(__file__).with_name("web_static")


class AppHandler(BaseHTTPRequestHandler):
    service: TraderService
    ingestion: IngestionService
    jobs: IngestionJobManager

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._serve_file("index.html", "text/html; charset=utf-8")
            return
        if parsed.path == "/ingestion":
            self._serve_file("ingestion.html", "text/html; charset=utf-8")
            return
        if parsed.path == "/app.js":
            self._serve_file("app.js", "application/javascript; charset=utf-8")
            return
        if parsed.path == "/ingestion.js":
            self._serve_file("ingestion.js", "application/javascript; charset=utf-8")
            return
        if parsed.path == "/styles.css":
            self._serve_file("styles.css", "text/css; charset=utf-8")
            return
        if parsed.path == "/api/hubs":
            self._send_json({"hubs": [hub.__dict__ for hub in self.service.known_hubs()]})
            return
        if parsed.path == "/api/ingestion/status":
            self._send_json(self.ingestion.status())
            return
        if parsed.path == "/api/ingestion/job":
            try:
                job_id = _required_query_param(parsed.query, "id")
                self._send_json(serialize_job(self.jobs.get_job(job_id)))
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        if parsed.path == "/api/ingestion/job/latest":
            latest = self.jobs.latest_job()
            self._send_json({"job": serialize_job(latest)} if latest is not None else {"job": None})
            return
        if parsed.path == "/api/health":
            self._send_json({"status": "ok"})
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/scan":
            if parsed.path == "/api/ingestion/run":
                self._handle_ingestion()
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON body."}, status=HTTPStatus.BAD_REQUEST)
            return

        try:
            result = self.service.scan(
                source_hub_key=_clean_optional(payload.get("sourceHub")),
                destination_hub_key=_clean_optional(payload.get("destinationHub")),
                source_region_id=_optional_int(payload.get("sourceRegionId")),
                source_location_id=_optional_int(payload.get("sourceLocationId")),
                destination_region_id=_optional_int(payload.get("destinationRegionId")),
                destination_location_id=_optional_int(payload.get("destinationLocationId")),
                strategy=str(payload.get("strategy", "instant")),
                minimum_profit=float(payload.get("minProfit", 20_000_000)),
                minimum_roi_percent=float(payload.get("minRoi", 8.0)),
                sales_tax=float(payload.get("salesTax", SALES_TAX_DEFAULT)),
                destination_broker_fee=float(payload.get("destinationBrokerFee", BROKER_FEE_DEFAULT)),
                top_n=int(payload.get("top", TOP_RESULTS_DEFAULT)),
                refresh=bool(payload.get("refresh", False)),
            )
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        except Exception as exc:  # pragma: no cover
            self._send_json({"error": f"Scan failed: {exc}"}, status=HTTPStatus.BAD_GATEWAY)
            return

        self._send_json(result)

    def _handle_ingestion(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON body."}, status=HTTPStatus.BAD_REQUEST)
            return

        try:
            mode = str(payload.get("mode", "known-hubs"))
            refresh = bool(payload.get("refresh", True))
            hub_key = _clean_optional(payload.get("hubKey"))
            result = serialize_job(self.jobs.start_job(mode=mode, hub_key=hub_key, refresh=refresh))
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        except Exception as exc:  # pragma: no cover
            self._send_json({"error": f"Ingestion failed: {exc}"}, status=HTTPStatus.BAD_GATEWAY)
            return

        self._send_json(result)

    def log_message(self, format: str, *args) -> None:
        return

    def _serve_file(self, filename: str, content_type: str) -> None:
        path = STATIC_DIR / filename
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local EVE Station Trader web app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--cache-ttl", type=int, default=DEFAULT_CACHE_TTL_SECONDS)
    parser.add_argument("--datasource", default="tranquility")
    args = parser.parse_args()

    service = TraderService(cache_ttl=args.cache_ttl, datasource=args.datasource)
    ingestion = IngestionService(service)
    jobs = IngestionJobManager(ingestion)
    handler = type("BoundAppHandler", (AppHandler,), {"service": service, "ingestion": ingestion, "jobs": jobs})
    server = ThreadingHTTPServer((args.host, args.port), handler)

    print(f"EVE Station Trader running on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.server_close()
    return 0


def _clean_optional(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _required_query_param(query: str, name: str) -> str:
    from urllib.parse import parse_qs

    values = parse_qs(query).get(name)
    if not values or not values[0]:
        raise ValueError(f"Missing query parameter: {name}")
    return values[0]


if __name__ == "__main__":
    sys.exit(main())
