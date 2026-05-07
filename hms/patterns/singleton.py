"""
Singleton Pattern — DatabaseSingleton
======================================
Ensures a single shared pyodbc database-connection instance across the
entire application.  The connection is created lazily on the first call to
``get_instance()`` and is reused on every subsequent call.  If the
connection becomes stale or is closed, ``get_connection()`` transparently
reconnects so callers never have to handle that themselves.

Usage
-----
    from hms.patterns.singleton import DatabaseSingleton

    singleton = DatabaseSingleton.get_instance(connection_params)
    conn = singleton.get_connection()   # always returns a live connection
"""

import threading
import pyodbc


class DatabaseSingleton:
    """
    Thread-safe Singleton database-connection manager.

    Only one instance is ever created per Python process.  All callers
    share the same underlying ``pyodbc`` connection, which is
    automatically re-established when it is found to be closed or broken.
    """

    _instance = None          # The one and only DatabaseSingleton object
    _lock = threading.Lock()  # Protects creation and connection access

    # ------------------------------------------------------------------ #
    #  Private constructor                                                 #
    # ------------------------------------------------------------------ #

    def __init__(self, connection_params: dict):
        if connection_params is None:
            raise ValueError("connection_params must not be None.")
        self._connection_params = connection_params
        self._connection = None
        self._conn_lock = threading.Lock()  # Guards the live connection obj

    # ------------------------------------------------------------------ #
    #  Singleton access                                                    #
    # ------------------------------------------------------------------ #

    @classmethod
    def get_instance(cls, connection_params: dict = None) -> "DatabaseSingleton":
        """
        Return the singleton instance, creating it if necessary.

        Parameters
        ----------
        connection_params : dict
            Must be supplied on the *first* call (when no instance exists
            yet).  Subsequent calls may omit it — the cached instance is
            returned unchanged.

        Returns
        -------
        DatabaseSingleton
        """
        if cls._instance is None:
            with cls._lock:
                # Double-checked locking — re-check inside the lock.
                if cls._instance is None:
                    if connection_params is None:
                        raise RuntimeError(
                            "DatabaseSingleton has not been initialised. "
                            "Call get_instance(connection_params) first."
                        )
                    cls._instance = cls(connection_params)
                    print("[DatabaseSingleton] Instance created.")
        return cls._instance

    @classmethod
    def reset(cls):
        """
        Destroy the current singleton (used in tests or on config change).
        Closes any open connection before resetting.
        """
        with cls._lock:
            if cls._instance is not None:
                try:
                    if cls._instance._connection:
                        cls._instance._connection.close()
                except Exception:
                    pass
            cls._instance = None
            print("[DatabaseSingleton] Instance reset.")

    # ------------------------------------------------------------------ #
    #  Connection management                                               #
    # ------------------------------------------------------------------ #

    def _build_connection_string(self) -> str:
        """Build the ODBC connection string from stored params."""
        params = self._connection_params
        driver   = params.get("driver", "ODBC Driver 17 for SQL Server")
        server   = params.get("server", "")
        database = params.get("database", "")
        username = params.get("username")
        password = params.get("password")

        conn_str = (
            f"DRIVER={{{driver}}};"
            f"SERVER={server};"
            f"DATABASE={database};"
        )
        if username and password:
            conn_str += f"UID={username};PWD={password};"
        else:
            conn_str += "Trusted_Connection=yes;"
        return conn_str

    def _is_connection_alive(self) -> bool:
        """Return True if the stored connection is open and responsive."""
        if self._connection is None:
            return False
        try:
            # A cheap no-op query to probe the connection.
            cursor = self._connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except Exception:
            return False

    def get_connection(self) -> pyodbc.Connection:
        """
        Return the shared ``pyodbc`` connection.

        If the connection has not been opened yet, or has been closed /
        dropped, a new one is created transparently.

        Returns
        -------
        pyodbc.Connection
            A live, ready-to-use database connection.
        """
        with self._conn_lock:
            if not self._is_connection_alive():
                print("[DatabaseSingleton] Opening new pyodbc connection.")
                self._connection = pyodbc.connect(
                    self._build_connection_string()
                )
                self._connection.autocommit = False
            return self._connection

    def close(self):
        """Explicitly close the shared connection (e.g. on app teardown)."""
        with self._conn_lock:
            if self._connection is not None:
                try:
                    self._connection.close()
                    print("[DatabaseSingleton] Connection closed.")
                except Exception:
                    pass
                finally:
                    self._connection = None

    # ------------------------------------------------------------------ #
    #  Dunder helpers                                                      #
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        status = "connected" if self._is_connection_alive() else "disconnected"
        return f"<DatabaseSingleton [{status}]>"
