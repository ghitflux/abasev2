from __future__ import annotations

import io
import tempfile
from datetime import date
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase, override_settings

from apps.accounts.models import User
from apps.associados.models import Associado
from apps.importacao.models import (
    ArquivoRetorno,
    ArquivoRetornoItem,
    ImportacaoLog,
    PagamentoMensalidade,
)
from apps.refinanciamento.models import AjusteValor, Item, Refinanciamento


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class CleanupFinanceDomainDataCommandTestCase(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            email="admin@abase.local",
            password="Senha@123",
            first_name="Admin",
            last_name="ABASE",
            is_active=True,
        )
        self.associado = Associado.objects.create(
            nome_completo="Associado Teste",
            cpf_cnpj="12345678900",
            email="associado@abase.local",
            telefone="86999999999",
        )

    def test_command_requires_explicit_mode(self):
        with self.assertRaises(CommandError):
            call_command("cleanup_finance_domain_data")

    def test_dry_run_reports_counts_without_changing_database_or_files(self):
        arquivo_path = default_storage.save(
            "arquivos_retorno/retorno-dry-run.txt",
            ContentFile(b"retorno"),
        )
        arquivo = ArquivoRetorno.objects.create(
            arquivo_nome="retorno-dry-run.txt",
            arquivo_url=arquivo_path,
            formato=ArquivoRetorno.Formato.TXT,
            orgao_origem="ETIPI",
            competencia=date(2025, 2, 1),
            uploaded_by=self.user,
        )
        ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=1,
            cpf_cnpj="12345678900",
            matricula_servidor="MAT-1",
            nome_servidor="Associado Teste",
            competencia="02/2025",
            valor_descontado=Decimal("30.00"),
        )
        ImportacaoLog.objects.create(
            arquivo_retorno=arquivo,
            tipo=ImportacaoLog.Tipo.UPLOAD,
            mensagem="Upload teste",
        )
        PagamentoMensalidade.objects.create(
            created_by=self.user,
            import_uuid="uuid-dry-run",
            referencia_month=date(2025, 2, 1),
            cpf_cnpj="12345678900",
            associado=self.associado,
            valor=Decimal("30.00"),
            source_file_path=arquivo_path,
        )

        stdout = io.StringIO()
        call_command("cleanup_finance_domain_data", "--dry-run", stdout=stdout)
        output = stdout.getvalue()

        self.assertIn("importacao_pagamentomensalidade: 1 registros", output)
        self.assertIn("importacao_arquivoretorno: 1 registros", output)
        self.assertIn("Arquivos de retorno candidatos: 1", output)
        self.assertIn("Nenhuma alteração foi aplicada", output)

        self.assertEqual(PagamentoMensalidade.objects.count(), 1)
        self.assertEqual(ArquivoRetorno.objects.count(), 1)
        self.assertEqual(ArquivoRetornoItem.objects.count(), 1)
        self.assertEqual(ImportacaoLog.objects.count(), 1)
        self.assertTrue(default_storage.exists(arquivo_path))

    def test_execute_removes_target_rows_files_and_resets_primary_keys(self):
        arquivo_path = default_storage.save(
            "arquivos_retorno/retorno-execucao.txt",
            ContentFile(b"retorno"),
        )
        arquivo = ArquivoRetorno.objects.create(
            arquivo_nome="retorno-execucao.txt",
            arquivo_url=arquivo_path,
            formato=ArquivoRetorno.Formato.TXT,
            orgao_origem="ETIPI",
            competencia=date(2025, 3, 1),
            uploaded_by=self.user,
        )
        ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=1,
            cpf_cnpj="12345678900",
            matricula_servidor="MAT-2",
            nome_servidor="Associado Teste",
            competencia="03/2025",
            valor_descontado=Decimal("30.00"),
        )
        ImportacaoLog.objects.create(
            arquivo_retorno=arquivo,
            tipo=ImportacaoLog.Tipo.BAIXA,
            mensagem="Baixa teste",
        )
        pagamento = PagamentoMensalidade.objects.create(
            created_by=self.user,
            import_uuid="uuid-execucao",
            referencia_month=date(2025, 3, 1),
            cpf_cnpj="12345678900",
            associado=self.associado,
            valor=Decimal("30.00"),
            source_file_path=arquivo_path,
        )
        refinanciamento = Refinanciamento.objects.create(
            associado=self.associado,
            solicitado_por=self.user,
            competencia_solicitada=date(2025, 3, 1),
            cpf_cnpj_snapshot=self.associado.cpf_cnpj,
            nome_snapshot=self.associado.nome_completo,
        )
        Item.objects.create(
            refinanciamento=refinanciamento,
            pagamento_mensalidade=pagamento,
            referencia_month=date(2025, 3, 1),
            valor=Decimal("30.00"),
        )

        stdout = io.StringIO()
        call_command("cleanup_finance_domain_data", "--execute", stdout=stdout)
        output = stdout.getvalue()

        self.assertIn("Arquivos removidos: 1", output)
        self.assertIn("Auto-increment resetado via TRUNCATE", output)

        self.assertEqual(PagamentoMensalidade.objects.count(), 0)
        self.assertEqual(ArquivoRetorno.objects.count(), 0)
        self.assertEqual(ArquivoRetornoItem.objects.count(), 0)
        self.assertEqual(ImportacaoLog.objects.count(), 0)
        self.assertEqual(Refinanciamento.objects.count(), 0)
        self.assertEqual(Item.objects.count(), 0)
        self.assertFalse(default_storage.exists(arquivo_path))

        novo_pagamento = PagamentoMensalidade.objects.create(
            created_by=self.user,
            import_uuid="uuid-novo",
            referencia_month=date(2025, 4, 1),
            cpf_cnpj="12345678900",
        )
        novo_arquivo = ArquivoRetorno.objects.create(
            arquivo_nome="novo.txt",
            arquivo_url="arquivos_retorno/novo.txt",
            formato=ArquivoRetorno.Formato.TXT,
            orgao_origem="ETIPI",
            competencia=date(2025, 4, 1),
            uploaded_by=self.user,
        )
        self.assertEqual(novo_pagamento.id, 1)
        self.assertEqual(novo_arquivo.id, 1)

    def test_execute_tolerates_missing_return_file(self):
        arquivo = ArquivoRetorno.objects.create(
            arquivo_nome="retorno-ausente.txt",
            arquivo_url="arquivos_retorno/retorno-ausente.txt",
            formato=ArquivoRetorno.Formato.TXT,
            orgao_origem="ETIPI",
            competencia=date(2025, 5, 1),
            uploaded_by=self.user,
        )
        ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=1,
            cpf_cnpj="12345678900",
            matricula_servidor="MAT-3",
            nome_servidor="Associado Teste",
            competencia="05/2025",
            valor_descontado=Decimal("30.00"),
        )

        stdout = io.StringIO()
        call_command("cleanup_finance_domain_data", "--execute", stdout=stdout)
        output = stdout.getvalue()

        self.assertIn("não encontrados: 1", output)
        self.assertEqual(ArquivoRetorno.objects.count(), 0)
        self.assertEqual(ArquivoRetornoItem.objects.count(), 0)

    def test_execute_aborts_when_out_of_scope_dependency_points_to_refinanciamento(self):
        refinanciamento = Refinanciamento.objects.create(
            associado=self.associado,
            solicitado_por=self.user,
            competencia_solicitada=date(2025, 6, 1),
            cpf_cnpj_snapshot=self.associado.cpf_cnpj,
            nome_snapshot=self.associado.nome_completo,
        )
        AjusteValor.objects.create(
            refinanciamento=refinanciamento,
            valor_novo=Decimal("10.00"),
        )
        arquivo_path = default_storage.save(
            "arquivos_retorno/retorno-bloqueado.txt",
            ContentFile(b"retorno"),
        )
        ArquivoRetorno.objects.create(
            arquivo_nome="retorno-bloqueado.txt",
            arquivo_url=arquivo_path,
            formato=ArquivoRetorno.Formato.TXT,
            orgao_origem="ETIPI",
            competencia=date(2025, 6, 1),
            uploaded_by=self.user,
        )

        with self.assertRaises(CommandError) as exc:
            call_command("cleanup_finance_domain_data", "--execute")

        self.assertIn("refinanciamento_ajustevalor", str(exc.exception))
        self.assertEqual(Refinanciamento.objects.count(), 1)
        self.assertEqual(AjusteValor.objects.count(), 1)
        self.assertEqual(ArquivoRetorno.objects.count(), 1)
        self.assertTrue(default_storage.exists(arquivo_path))

    def test_execute_is_noop_when_target_tables_are_empty(self):
        stdout = io.StringIO()
        call_command("cleanup_finance_domain_data", "--execute", stdout=stdout)
        output = stdout.getvalue()

        self.assertIn("Arquivos removidos: 0", output)
        self.assertIn("importacao_pagamentomensalidade: 0 registros removidos", output)
        self.assertEqual(PagamentoMensalidade.objects.count(), 0)
        self.assertEqual(ArquivoRetorno.objects.count(), 0)
        self.assertEqual(Refinanciamento.objects.count(), 0)
