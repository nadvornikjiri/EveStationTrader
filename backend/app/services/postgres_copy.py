from collections.abc import Iterable
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
