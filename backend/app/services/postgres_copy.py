from collections.abc import Iterable
from pathlib import Path
from typing import cast

from psycopg import Connection as PsycopgConnection
from sqlalchemy.orm import Session


def copy_rows(
    session: Session,
    *,
    table_name: str,
    columns: tuple[str, ...],
    rows: Iterable[tuple[object, ...]],
) -> None:
    connection = session.connection()
    raw_connection = cast(PsycopgConnection, connection.connection.driver_connection)
    copy_sql = f"COPY {table_name} ({', '.join(columns)}) FROM STDIN"
    with raw_connection.cursor().copy(copy_sql) as copy:
        for row in rows:
            copy.write_row(row)


def copy_delimited_file(
    session: Session,
    *,
    table_name: str,
    file_path: str | Path,
    columns: tuple[str, ...] | None = None,
    delimiter: str = ";",
    header: bool = True,
) -> None:
    connection = session.connection()
    raw_connection = cast(PsycopgConnection, connection.connection.driver_connection)
    csv_mode = f"FORMAT CSV, DELIMITER '{delimiter}'"
    if header:
        csv_mode = f"{csv_mode}, HEADER TRUE"
    destination = table_name if columns is None else f"{table_name} ({', '.join(columns)})"
    copy_sql = f"COPY {destination} FROM STDIN WITH ({csv_mode})"
    with raw_connection.cursor().copy(copy_sql) as copy:
        with Path(file_path).open("r", encoding="utf-8", newline="") as source:
            while chunk := source.read(1024 * 1024):
                copy.write(chunk)
