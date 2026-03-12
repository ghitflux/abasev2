from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from django.core.exceptions import ImproperlyConfigured


def configure_local_mysqlclient() -> None:
    try:
        import MySQLdb  # type: ignore  # noqa: F401
    except ImportError:
        import pymysql

        pymysql.version_info = (2, 2, 6, "final", 0)
        pymysql.__version__ = "2.2.6"
        pymysql.install_as_MySQLdb()

    from django.db.backends.mysql.features import DatabaseFeatures

    DatabaseFeatures.minimum_database_version = property(
        lambda self: (10, 4) if self.connection.mysql_is_mariadb else (8, 0, 11)
    )
    DatabaseFeatures.can_return_columns_from_insert = property(
        lambda self: self.connection.mysql_is_mariadb
        and self.connection.mysql_version >= (10, 5)
    )
    DatabaseFeatures.can_return_rows_from_bulk_insert = property(
        lambda self: self.can_return_columns_from_insert
    )

    if os.environ.get("MARIADB_PLUGIN_DIR"):
        return

    plugin_dir = (
        Path.home()
        / ".local"
        / "mysqlclient-deps"
        / "usr"
        / "lib"
        / "x86_64-linux-gnu"
        / "libmariadb3"
        / "plugin"
    )
    if plugin_dir.exists():
        os.environ.setdefault("MARIADB_PLUGIN_DIR", str(plugin_dir))


def enforce_mysql_only(
    databases: Mapping[str, Mapping[str, object]], source: str
) -> None:
    for alias, config in databases.items():
        engine = str(config.get("ENGINE") or "").strip()
        if engine != "django.db.backends.mysql":
            raise ImproperlyConfigured(
                f"{source}: banco '{alias}' configurado com '{engine or 'vazio'}'. "
                "Este projeto suporta apenas MySQL; SQLite nao e permitido."
            )
