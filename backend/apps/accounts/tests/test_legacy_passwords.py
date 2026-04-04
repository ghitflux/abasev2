from __future__ import annotations

import bcrypt
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import identify_hasher
from django.db import connection
from django.test import TestCase, override_settings

from apps.accounts.hashers import encode_legacy_bcrypt_hash
from apps.accounts.management.commands.import_legacy_data import Command
from apps.accounts.models import Role, User


@override_settings(
    PASSWORD_HASHERS=[
        "django.contrib.auth.hashers.MD5PasswordHasher",
        "apps.accounts.hashers.LegacyLaravelBcryptPasswordHasher",
    ]
)
class LegacyPasswordAuthTestCase(TestCase):
    def _legacy_hash(self, password: str) -> str:
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
        return hashed.replace("$2b$", "$2y$", 1)

    def test_authenticate_with_legacy_bcrypt_hash(self):
        user = User.objects.create(
            email="admin@abase.com",
            first_name="Admin",
            last_name="",
            is_active=True,
            password=encode_legacy_bcrypt_hash(self._legacy_hash("Segredo@123")),
        )

        authenticated = authenticate(username="admin@abase.com", password="Segredo@123")

        self.assertIsNotNone(authenticated)
        self.assertEqual(authenticated.pk, user.pk)

        user.refresh_from_db()
        self.assertEqual(identify_hasher(user.password).algorithm, "md5")

    def test_import_users_preserva_hash_legado_em_usuario_existente(self):
        user = User.objects.create(
            email="tesouraria@abase.com",
            first_name="Tesouraria",
            last_name="",
            is_active=True,
        )
        user.set_unusable_password()
        user.save(update_fields=["password", "updated_at"])

        command = Command()
        command.stdout.write = lambda *_args, **_kwargs: None
        command._user_map = {}

        legacy_hash = self._legacy_hash("SenhaAntiga@123")
        command._import_users(
            [
                {
                    "id": "2",
                    "name": "'tesouraria'",
                    "email": "'tesouraria@abase.com'",
                    "password": f"'{legacy_hash}'",
                    "must_set_password": "0",
                    "profile_photo_path": "NULL",
                }
            ]
        )

        user.refresh_from_db()
        self.assertTrue(user.password.startswith("legacy_bcrypt$"))

        authenticated = authenticate(
            username="tesouraria@abase.com",
            password="SenhaAntiga@123",
        )
        self.assertIsNotNone(authenticated)


@override_settings(
    PASSWORD_HASHERS=[
        "django.contrib.auth.hashers.MD5PasswordHasher",
        "apps.accounts.hashers.LegacyLaravelBcryptPasswordHasher",
    ],
    AUTHENTICATION_BACKENDS=[
        "django.contrib.auth.backends.ModelBackend",
        "apps.accounts.backends.LegacyLaravelUserBackend",
    ],
)
class LegacyDatabaseSyncAuthTestCase(TestCase):
    @staticmethod
    def _legacy_hash(password: str) -> str:
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
        return hashed.replace("$2b$", "$2y$", 1)

    @classmethod
    def tearDownClass(cls):
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS role_user")
            cursor.execute("DROP TABLE IF EXISTS roles")
            cursor.execute("DROP TABLE IF EXISTS users")
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS role_user")
            cursor.execute("DROP TABLE IF EXISTS roles")
            cursor.execute("DROP TABLE IF EXISTS users")
            cursor.execute(
                """
                CREATE TABLE users (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    password VARCHAR(255) NULL,
                    must_set_password TINYINT(1) NOT NULL DEFAULT 1,
                    profile_photo_path VARCHAR(2048) NULL,
                    created_at DATETIME NULL,
                    updated_at DATETIME NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE roles (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL UNIQUE
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE role_user (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    role_id BIGINT UNSIGNED NOT NULL,
                    user_id BIGINT UNSIGNED NOT NULL,
                    created_at DATETIME NULL,
                    updated_at DATETIME NULL
                )
                """
            )
            cursor.execute(
                """
                INSERT INTO users (name, email, password, must_set_password, profile_photo_path)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [
                    "Admin Legacy",
                    "admin@abase.com",
                    cls._legacy_hash("Segredo@123"),
                    0,
                    "avatars/admin.png",
                ],
            )
            cursor.execute("INSERT INTO roles (id, name) VALUES (%s, %s)", [1, "admin"])
            cursor.execute(
                """
                INSERT INTO role_user (role_id, user_id)
                VALUES (%s, %s)
                """,
                [1, 1],
            )

    def test_authenticate_syncs_user_from_legacy_tables(self):
        authenticated = authenticate(
            username="admin@abase.com",
            password="Segredo@123",
        )

        self.assertIsNotNone(authenticated)

        user = User.objects.get(email="admin@abase.com")
        self.assertEqual(authenticated.pk, user.pk)
        self.assertEqual(user.first_name, "Admin")
        self.assertEqual(user.last_name, "Legacy")
        self.assertTrue(user.password.startswith("legacy_bcrypt$"))
        self.assertFalse(user.must_set_password)
        self.assertEqual(user.profile_photo_path, "avatars/admin.png")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(list(user.roles.values_list("codigo", flat=True)), ["ADMIN"])

        role = Role.objects.get(codigo="ADMIN")
        self.assertEqual(role.nome, "Administrador")
