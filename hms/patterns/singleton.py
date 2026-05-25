"""
Singleton Pattern — DatabaseSingleton (psycopg2 / PostgreSQL)
=============================================================
Retained for architectural completeness.  The active database layer
(hms/__init__.py Database class) opens a fresh connection per request,
so this singleton is no longer used at runtime.  It is kept so that
any code that imports DatabaseSingleton does not break.
"""

import threading


class DatabaseSingleton:
    """
    Thread-safe Singleton stub for PostgreSQL.

    The psycopg2 connection pool is managed by the Database class in
    hms/__init__.py.  This class exists only for import compatibility.
    """

    _instance = None
    _lock = threading.Lock()

    def __init__(self, connection_params: dict):
        self._connection_params = connection_params or {}
        self._connection = None

    @classmethod
    def get_instance(cls, connection_params: dict = None) -> "DatabaseSingleton":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(connection_params or {})
        return cls._instance

    @classmethod
    def reset(cls):
        with cls._lock:
            cls._instance = None

    def get_connection(self):
        """Delegate to the module-level db object."""
        from hms import db
        return db.get_connection()

    def close(self):
        pass

    def __repr__(self):
        return "<DatabaseSingleton [psycopg2 stub]>"
