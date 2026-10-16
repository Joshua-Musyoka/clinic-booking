from collections.abc import Generator, Sequence
from contextlib import contextmanager
from typing import Any

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import DictCursor

from app.config import get_settings


def get_connection() -> Connection:
    """Create a connection to the configured MariaDB database."""
    settings = get_settings()

    return pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password.get_secret_value(),
        database=settings.mysql_database,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
        connect_timeout=5,
        read_timeout=10,
        write_timeout=10,
    )


@contextmanager
def database_connection() -> Generator[Connection, None, None]:
    """Yield a database connection and always close it."""
    connection = get_connection()

    try:
        yield connection
    finally:
        connection.close()


def execute_procedure(
    cursor: DictCursor,
    procedure_name: str,
    parameters: Sequence[Any] = (),
) -> list[dict[str, Any]]:
    """
    Execute a stored procedure and return its first result set.

    Procedure names must be internal, trusted identifiers—not user input.
    Parameter values are passed separately to prevent SQL injection.
    Additional result sets are consumed so the connection remains usable.
    """
    if not procedure_name.replace("_", "").isalnum():
        raise ValueError("Invalid stored procedure name.")

    placeholders = ", ".join(["%s"] * len(parameters))
    statement = f"CALL {procedure_name}({placeholders})"

    cursor.execute(statement, tuple(parameters))

    rows: list[dict[str, Any]] = []

    if cursor.description is not None:
        rows = list(cursor.fetchall())

    while cursor.nextset():
        if cursor.description is not None:
            cursor.fetchall()

    return rows