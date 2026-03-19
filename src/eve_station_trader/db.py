from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .models import MarketOrder


class MarketDatabase:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS market_orders (
                    region_id INTEGER NOT NULL,
                    type_id INTEGER NOT NULL,
                    location_id INTEGER NOT NULL,
                    is_buy_order INTEGER NOT NULL,
                    price REAL NOT NULL,
                    volume_remain INTEGER NOT NULL,
                    min_volume INTEGER NOT NULL,
                    order_range TEXT NOT NULL,
                    fetched_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_market_orders_region_location_type
                ON market_orders(region_id, location_id, type_id);

                CREATE INDEX IF NOT EXISTS idx_market_orders_region_type_side
                ON market_orders(region_id, type_id, is_buy_order);

                CREATE TABLE IF NOT EXISTS ingestion_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    region_id INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    orders_written INTEGER NOT NULL,
                    completed_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS item_names (
                    type_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def replace_region_orders(self, region_id: int, orders: list[MarketOrder], source: str) -> int:
        fetched_at = _utc_now()
        rows = [
            (
                region_id,
                order.type_id,
                order.location_id,
                1 if order.is_buy_order else 0,
                order.price,
                order.volume_remain,
                order.min_volume,
                order.range,
                fetched_at,
            )
            for order in orders
        ]

        with self.connect() as connection:
            connection.execute("DELETE FROM market_orders WHERE region_id = ?", (region_id,))
            connection.executemany(
                """
                INSERT INTO market_orders (
                    region_id,
                    type_id,
                    location_id,
                    is_buy_order,
                    price,
                    volume_remain,
                    min_volume,
                    order_range,
                    fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            connection.execute(
                """
                INSERT INTO ingestion_runs (region_id, source, orders_written, completed_at)
                VALUES (?, ?, ?, ?)
                """,
                (region_id, source, len(rows), fetched_at),
            )
        return len(rows)

    def get_region_orders(self, region_id: int) -> list[MarketOrder]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT type_id, location_id, is_buy_order, price, volume_remain, min_volume, order_range
                FROM market_orders
                WHERE region_id = ?
                """,
                (region_id,),
            ).fetchall()
        return [
            MarketOrder(
                type_id=int(row["type_id"]),
                location_id=int(row["location_id"]),
                is_buy_order=bool(row["is_buy_order"]),
                price=float(row["price"]),
                volume_remain=int(row["volume_remain"]),
                min_volume=int(row["min_volume"]),
                range=str(row["order_range"]),
            )
            for row in rows
        ]

    def region_order_count(self, region_id: int) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM market_orders WHERE region_id = ?",
                (region_id,),
            ).fetchone()
        return int(row["count"]) if row else 0

    def region_snapshot(self, region_id: int) -> dict[str, object] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT completed_at, orders_written, source
                FROM ingestion_runs
                WHERE region_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (region_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "region_id": region_id,
            "completed_at": str(row["completed_at"]),
            "orders_written": int(row["orders_written"]),
            "source": str(row["source"]),
        }

    def all_region_snapshots(self) -> list[dict[str, object]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT region_id, source, orders_written, completed_at
                FROM ingestion_runs
                WHERE id IN (
                    SELECT MAX(id)
                    FROM ingestion_runs
                    GROUP BY region_id
                )
                ORDER BY completed_at DESC
                """
            ).fetchall()
        return [
            {
                "region_id": int(row["region_id"]),
                "source": str(row["source"]),
                "orders_written": int(row["orders_written"]),
                "completed_at": str(row["completed_at"]),
            }
            for row in rows
        ]

    def upsert_item_names(self, names: dict[int, str]) -> None:
        if not names:
            return

        updated_at = _utc_now()
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO item_names (type_id, name, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(type_id) DO UPDATE SET
                    name = excluded.name,
                    updated_at = excluded.updated_at
                """,
                [(type_id, name, updated_at) for type_id, name in names.items()],
            )

    def get_item_names(self, type_ids: set[int]) -> dict[int, str]:
        if not type_ids:
            return {}

        placeholders = ",".join("?" for _ in type_ids)
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT type_id, name FROM item_names WHERE type_id IN ({placeholders})",
                tuple(sorted(type_ids)),
            ).fetchall()
        return {int(row["type_id"]): str(row["name"]) for row in rows}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
