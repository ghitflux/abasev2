from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.runtime import enforce_mysql_only


class DatabaseEnginePolicyTestCase(SimpleTestCase):
    def test_accepts_mysql_engine(self):
        enforce_mysql_only(
            {"default": {"ENGINE": "django.db.backends.mysql"}},
            "tests.database",
        )

    def test_rejects_sqlite_engine(self):
        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "Este projeto suporta apenas MySQL; SQLite nao e permitido.",
        ):
            enforce_mysql_only(
                {"default": {"ENGINE": "django.db.backends.sqlite3"}},
                "tests.database",
            )
