"""
db_queries.py — low-level query helpers for psycopg2 (PostgreSQL).

psycopg2 uses %s positional placeholders.
Named :param style is converted automatically by _convert_named_params().
"""

import re
from types import SimpleNamespace
from hms import db


def is_sql_server():
    """Always False — we are on PostgreSQL."""
    return False


def is_postgres():
    return True


def _convert_named_params(sql, params):
    """Convert :name style parameters to %s positional style for psycopg2.

    Returns (converted_sql, ordered_values_tuple_or_None).
    If params is already a list/tuple it is returned unchanged.
    """
    if params is None:
        return sql, None
    if not isinstance(params, dict):
        return sql, params

    ordered_values = []

    def _replacer(match):
        name = match.group(1)
        ordered_values.append(params.get(name))
        return "%s"

    converted_sql = re.sub(r":(\w+)", _replacer, sql)
    return converted_sql, tuple(ordered_values) if ordered_values else None


def fetch_rows(sql, params=None):
    """Execute a SELECT and return a list of dicts."""
    import psycopg2.extras
    conn = None
    try:
        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql, params = _convert_named_params(sql, params)
        if params is not None:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)

        if cursor.description is None:
            cursor.close()
            return []

        rows = [dict(row) for row in cursor.fetchall()]
        cursor.close()
        return rows
    except Exception as e:
        print(f"Query Error: {e}")
        raise
    finally:
        if conn:
            conn.close()


def exec_procedure(name, params=None):
    """Compatibility shim — not used on PostgreSQL (no stored procedures).
    Raises NotImplementedError so callers know to use inline SQL instead.
    """
    raise NotImplementedError(
        f"exec_procedure('{name}') called on PostgreSQL — use inline SQL via fetch_rows()."
    )


def rows_to_objects(rows):
    return [
        SimpleNamespace(**dict(row)) if not isinstance(row, dict) else SimpleNamespace(**row)
        for row in rows
    ]
