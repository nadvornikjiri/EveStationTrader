from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class JsonCache:
    def __init__(self, root: Path, ttl_seconds: int) -> None:
        self.root = root
        self.ttl_seconds = ttl_seconds
        self.root.mkdir(parents=True, exist_ok=True)

    def load(self, key: str) -> Any | None:
        path = self.root / f"{key}.json"
        if not path.exists():
            return None

        payload = json.loads(path.read_text(encoding="utf-8"))
        timestamp = payload.get("timestamp")
        if not isinstance(timestamp, (int, float)):
            return None

        if time.time() - float(timestamp) > self.ttl_seconds:
            return None

        return payload.get("data")

    def store(self, key: str, data: Any) -> None:
        path = self.root / f"{key}.json"
        payload = {
            "timestamp": time.time(),
            "data": data,
        }
        path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
