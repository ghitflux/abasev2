from __future__ import annotations

import io
import tempfile
from datetime import date
from decimal import Decimal

from django.core.management import call_command
from django.test import TransactionTestCase, override_settings

from apps.accounts.models import MobileAccessToken, Role, User
from apps.associados.models import Associado
from apps.importacao.models import ArquivoRetorno, PagamentoMensalidade


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ResetDatabasePreservingAuthCommandTestCase(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        super().setUp()
        self.role = Role.objects.create(codigo="ADMIN", nome="Administrador")
        self.user = User.objects.create_user(
            email="admin@abase.local",
            password="Senha@123",
            first_name="Admin",
            last_name="ABASE",
            is_active=True,
        )
        self.user.roles.add(self.role)
        MobileAccessToken.objects.create(
            user=self.user,
            key="k" * 64,
            token_prefix="kkkk",
            scope=MobileAccessToken.Scope.LEGACY_APP,
            name="teste",
        )
        self.associado = Associado.objects.create(
            nome_completo="Associado Teste",
            cpf_cnpj="12345678900",
            email="associado@abase.local",
            telefone="86999999999",
        )
        ArquivoRetorno.objects.create(
            arquivo_nome="retorno.txt",
            arquivo_url="arquivos_retorno/retorno.txt",
            formato=ArquivoRetorno.Formato.TXT,
            orgao_origem="ETIPI",
            competencia=date(2025, 10, 1),
            uploaded_by=self.user,
        )
        PagamentoMensalidade.objects.create(
            created_by=self.user,
            import_uuid="uuid",
            referencia_month=date(2025, 10, 1),
            cpf_cnpj=self.associado.cpf_cnpj,
            associado=self.associado,
            valor=Decimal("30.00"),
            source_file_path="arquivos_retorno/retorno.txt",
        )

    def test_dry_run_only_reports_tables(self):
        stdout = io.StringIO()
        call_command("reset_database_preserving_auth", "--dry-run", stdout=stdout)
        output = stdout.getvalue()

        self.assertIn("accounts_user", output)
        self.assertIn("associados_associado", output)
        self.assertEqual(User.all_objects.count(), 1)
        self.assertEqual(Associado.objects.count(), 1)
        self.assertEqual(ArquivoRetorno.objects.count(), 1)

    def test_execute_truncates_domain_tables_and_preserves_auth(self):
        call_command("reset_database_preserving_auth", "--execute")

        self.assertEqual(User.all_objects.count(), 1)
        self.assertEqual(Role.all_objects.count(), 1)
        self.assertEqual(MobileAccessToken.all_objects.count(), 1)
        self.assertEqual(self.user.user_roles.count(), 1)
        self.assertEqual(Associado.objects.count(), 0)
        self.assertEqual(ArquivoRetorno.objects.count(), 0)
        self.assertEqual(PagamentoMensalidade.objects.count(), 0)
