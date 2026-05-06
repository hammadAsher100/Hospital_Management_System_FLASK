import re
from types import SimpleNamespace
from hms import db


def is_sql_server():
    return True


def _convert_named_params(sql, params):
    """Convert :name style parameters to ? positional style for pyodbc.

    pyodbc does NOT support :name parameters — only ? placeholders.
    This helper rewrites the SQL and returns an ordered tuple of values.
    """
    if params is None:
        return sql, None
    if not isinstance(params, dict):
        # Already positional (tuple/list) — leave as-is
        return sql, params

    ordered_values = []

    def _replacer(match):
        name = match.group(1)
        ordered_values.append(params.get(name))
        return "?"

    converted_sql = re.sub(r":(\w+)", _replacer, sql)
    return converted_sql, tuple(ordered_values) if ordered_values else None


def fetch_rows(sql, params=None):
    """Execute SELECT query and return list of dictionaries."""
    conn = None
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        sql, params = _convert_named_params(sql, params)
        if params is not None:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)

        if cursor.description is None:
            cursor.close()
            return []

        columns = [column[0] for column in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        cursor.close()
        return rows
    except Exception as e:
        print(f"Query Error: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()


def exec_procedure(name, params=None):
    """Execute stored procedure and return results."""
    params = params or {}
    if params:
        placeholders = ", ".join(f"@{key}=?" for key in params.keys())
        sql = f"EXEC {name} {placeholders}"
        param_values = list(params.values())
    else:
        sql = f"EXEC {name}"
        param_values = None
    return fetch_rows(sql, param_values)


def rows_to_objects(rows):
    return [SimpleNamespace(**dict(row)) if hasattr(row, '__dict__') else SimpleNamespace(**row) for row in rows]
