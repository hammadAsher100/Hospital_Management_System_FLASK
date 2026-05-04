from types import SimpleNamespace

from sqlalchemy import text

from hms import db


def is_sql_server():
    return db.engine.dialect.name == "mssql"


def fetch_rows(sql, params=None):
    result = db.session.execute(text(sql), params or {})
    return result.mappings().all()


def exec_procedure(name, params=None):
    params = params or {}
    if params:
        placeholders = ", ".join(f"@{key}=:{key}" for key in params.keys())
        sql = f"EXEC {name} {placeholders}"
    else:
        sql = f"EXEC {name}"
    return fetch_rows(sql, params)


def rows_to_objects(rows):
    return [SimpleNamespace(**dict(row)) for row in rows]
