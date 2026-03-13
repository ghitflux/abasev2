from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.accounts.management.seed_utils import SeedUserSpec, ensure_access_users
from apps.accounts.models import User


class SeedUtilsTestCase(TestCase):
    def test_ensure_access_users_preserva_hash_existente(self):
        user = User.objects.create_user(
            email="admin@abase.local",
            password="HashAntigo@123",
            first_name="Original",
            last_name="User",
            is_active=True,
        )
        original_password_hash = user.password

        with patch(
            "apps.accounts.management.seed_utils.default_seed_user_specs",
            return_value=[
                SeedUserSpec(
                    role_code="ADMIN",
                    email="admin@abase.local",
                    first_name="Admin",
                    last_name="ABASE",
                    password="NovaSenha@123",
                    is_staff=True,
                    is_superuser=True,
                )
            ],
        ):
            ensure_access_users()

        user.refresh_from_db()
        self.assertEqual(user.password, original_password_hash)
        self.assertTrue(user.check_password("HashAntigo@123"))
        self.assertFalse(user.check_password("NovaSenha@123"))
        self.assertEqual(user.first_name, "Admin")
        self.assertEqual(user.last_name, "ABASE")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(list(user.roles.values_list("codigo", flat=True)), ["ADMIN"])
