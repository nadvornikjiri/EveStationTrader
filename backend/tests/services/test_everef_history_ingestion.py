from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import EsiHistoryDaily, Item, Region
from app.services.everef.history_ingestion import EveRefHistoryIngestionService
from tests.db_test_utils import build_test_session


def build_session() -> Session:
    return build_test_session()


def seed_region_and_item(session: Session) -> tuple[int, int]:
    # Use internal PKs (1, 2) that differ from EVE IDs (10000002, 34) to
    # verify the ingestion SQL joins on eve_id columns, not raw CSV values.
    region = Region(id=1, region_id=10000002, name="The Forge")
    item = Item(id=2, type_id=34, name="Tritanium", volume_m3=0.01, group_name="Mineral", category_name="Material")
    session.add_all([region, item])
    session.commit()
    return region.id, item.id


def test_ingest_history_file_raises_for_non_postgres(tmp_path) -> None:
    class SqliteBind:
        class dialect:
            name = "sqlite"

    class FakeSession:
        def get_bind(self) -> SqliteBind:
            return SqliteBind()

    csv_path = tmp_path / "history.csv"
    csv_path.write_text(
        "average,date,highest,lowest,order_count,volume,http_last_modified,region_id,type_id\n",
        encoding="utf-8",
    )

    with pytest.raises(NotImplementedError):
        EveRefHistoryIngestionService().ingest_history_file(FakeSession(), csv_path)  # type: ignore[arg-type]


@pytest.mark.integration
def test_ingest_history_file_replaces_existing_rows_and_runs_cancellation_checks(tmp_path) -> None:
    session = build_session()
    region_id, item_id = seed_region_and_item(session)
    session.add(
        EsiHistoryDaily(
            region_id=region_id,
            type_id=item_id,
            date=date(2026, 4, 10),
            average=1.0,
            highest=2.0,
            lowest=0.5,
            order_count=1,
            volume=10,
        )
    )
    session.commit()

    csv_path = tmp_path / "market-history-2026-04-10.csv"
    csv_path.write_text(
        "average,date,highest,lowest,order_count,volume,http_last_modified,region_id,type_id\n"
        "10.5,2026-04-10,11.0,9.5,7,999,2026-04-11T00:00:00Z,10000002,34\n"
        "12.0,2026-04-11,13.0,11.0,8,1000,2026-04-11T00:00:00Z,10000002,34\n",
        encoding="utf-8",
    )

    cancellation_calls: list[str] = []

    def cancellation_check() -> None:
        cancellation_calls.append("called")

    inserted = EveRefHistoryIngestionService().ingest_history_file(
        session,
        csv_path,
        cancellation_check=cancellation_check,
    )

    rows = session.scalars(select(EsiHistoryDaily).order_by(EsiHistoryDaily.date.asc())).all()

    assert inserted == 2
    assert cancellation_calls == ["called", "called"]
    assert [(row.region_id, row.type_id, row.date) for row in rows] == [
        (region_id, item_id, date(2026, 4, 10)),
        (region_id, item_id, date(2026, 4, 11)),
    ]
    assert rows[0].average == 10.5
    assert rows[0].highest == 11.0
    assert rows[0].lowest == 9.5
    assert rows[0].order_count == 7
    assert rows[0].volume == 999
    assert rows[1].average == 12.0
    session.close()
