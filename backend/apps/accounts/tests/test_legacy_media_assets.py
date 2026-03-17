from __future__ import annotations

import shutil
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings

from apps.accounts.legacy_media_assets import LegacyMediaAssetsService
from apps.associados.models import Associado, Documento
from apps.contratos.models import Contrato
from apps.importacao.models import PagamentoMensalidade
from apps.refinanciamento.models import Comprovante
from apps.esteira.models import DocIssue, DocReupload


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class LegacyMediaAssetsServiceTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.legacy_root = Path(tempfile.mkdtemp())
        self.user = get_user_model().objects.create_user(
            email="tester@abase.com",
            password="senha",
            first_name="Tester",
        )
        self.associado = Associado.objects.create(
            nome_completo="Associado Teste",
            cpf_cnpj="12345678900",
            matricula="MAT001",
            tipo_documento=Associado.TipoDocumento.CPF,
        )
        self.contrato = Contrato.objects.create(
            associado=self.associado,
            agente=self.user,
            codigo="CTR-TESTE-001",
            prazo_meses=3,
            valor_mensalidade=Decimal("300.00"),
            valor_liquido=Decimal("900.00"),
            valor_total_antecipacao=Decimal("900.00"),
        )

    def tearDown(self):
        shutil.rmtree(self.legacy_root, ignore_errors=True)
        super().tearDown()

    def _write_legacy_file(self, relative_path: str, content: bytes = b"ok") -> str:
        target = self.legacy_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return str(target)

    def test_syncs_all_supported_families_to_official_storage(self):
        self._write_legacy_file(
            "public/public/uploads/associados/1/documento-frente.pdf",
            b"cadastro",
        )
        self._write_legacy_file(
            "storage/storage/app/public/refinanciamentos/solicitacoes/2025-10_2025-11_2025-12/12345678900/1/termo.pdf",
            b"termo",
        )
        self._write_legacy_file(
            "public/public/storage/tesouraria/comprovantes/1/comprovante-associado.png",
            b"tesouraria",
        )
        self._write_legacy_file(
            "storage/storage/app/public/retornos/2025/12/manual.pdf",
            b"manual",
        )
        self._write_legacy_file(
            "public/public/storage/agent-reuploads/488/reupload.pdf",
            b"reupload",
        )
        self._write_legacy_file(
            "public/public/storage/agent_uploads/1/snapshot.png",
            b"snapshot",
        )

        documento = Documento.objects.create(
            associado=self.associado,
            tipo=Documento.Tipo.DOCUMENTO_FRENTE,
            arquivo="uploads/associados/1/documento-frente.pdf",
            origem=Documento.Origem.LEGADO_CADASTRO,
        )
        termo = Comprovante.objects.create(
            contrato=self.contrato,
            tipo=Comprovante.Tipo.TERMO_ANTECIPACAO,
            papel=Comprovante.Papel.OPERACIONAL,
            origem=Comprovante.Origem.LEGADO,
            arquivo="legacy/term.pdf",
            arquivo_referencia_path=(
                "refinanciamentos/solicitacoes/"
                "2025-10_2025-11_2025-12/12345678900/1/termo.pdf"
            ),
            enviado_por=self.user,
        )
        comprovante_tesouraria = Comprovante.objects.create(
            contrato=self.contrato,
            tipo=Comprovante.Tipo.COMPROVANTE_PAGAMENTO_ASSOCIADO,
            papel=Comprovante.Papel.ASSOCIADO,
            origem=Comprovante.Origem.EFETIVACAO_CONTRATO,
            arquivo="tesouraria/comprovantes/1/comprovante-associado.png",
            arquivo_referencia_path="tesouraria/comprovantes/1/comprovante-associado.png",
            enviado_por=self.user,
        )
        pagamento_manual = PagamentoMensalidade.objects.create(
            import_uuid="manual-1",
            referencia_month=date(2025, 12, 1),
            cpf_cnpj=self.associado.cpf_cnpj,
            associado=self.associado,
            manual_comprovante_path="retornos/2025/12/manual.pdf",
        )
        reupload = DocReupload.objects.create(
            doc_issue=DocIssue.objects.create(
                associado=self.associado,
                cpf_cnpj=self.associado.cpf_cnpj,
                analista=self.user,
                mensagem="Documento faltando",
                agent_uploads_json=[{"field": "termo_adesao", "relative_path": "storage/agent_uploads/1/snapshot.png"}],
            ),
            associado=self.associado,
            cpf_cnpj=self.associado.cpf_cnpj,
            contrato_codigo=self.contrato.codigo,
            file_original_name="reupload.pdf",
            file_stored_name="reupload.pdf",
            file_relative_path="storage/agent-reuploads/488/reupload.pdf",
        )

        payload = LegacyMediaAssetsService(legacy_root=self.legacy_root).run(
            execute=True,
        )

        documento.refresh_from_db()
        termo.refresh_from_db()
        comprovante_tesouraria.refresh_from_db()
        pagamento_manual.refresh_from_db()
        reupload.refresh_from_db()
        issue = reupload.doc_issue
        issue.refresh_from_db()

        self.assertEqual(payload["summary"]["updated"], 6)
        self.assertTrue(documento.arquivo.name.startswith("documentos/associados/12345678900/documento_frente/"))
        self.assertEqual(documento.arquivo_referencia_path, "uploads/associados/1/documento-frente.pdf")
        self.assertTrue(default_storage.exists(documento.arquivo.name))

        self.assertTrue(termo.arquivo.name.startswith("refinanciamentos/renovacoes/CTR-TESTE-001/termo/"))
        self.assertTrue(default_storage.exists(termo.arquivo.name))
        self.assertTrue(
            comprovante_tesouraria.arquivo.name.startswith(
                "refinanciamentos/efetivacao_contrato/CTR-TESTE-001/associado_"
            )
        )
        self.assertTrue(default_storage.exists(comprovante_tesouraria.arquivo.name))

        self.assertTrue(
            pagamento_manual.manual_comprovante_path.startswith(
                "pagamentos_mensalidades/comprovantes/2025/12/12345678900_"
            )
        )
        self.assertTrue(default_storage.exists(pagamento_manual.manual_comprovante_path))

        self.assertTrue(reupload.file_relative_path.startswith("esteira/reuploads/"))
        self.assertEqual(
            reupload.extras["legacy_path"],
            "storage/agent-reuploads/488/reupload.pdf",
        )
        self.assertTrue(default_storage.exists(reupload.file_relative_path))

        snapshot = issue.agent_uploads_json[0]
        self.assertEqual(snapshot["legacy_path"], "storage/agent_uploads/1/snapshot.png")
        self.assertTrue(snapshot["storage_path"].startswith("esteira/agent_uploads/"))
        self.assertTrue(snapshot["arquivo_disponivel_localmente"])

    def test_audit_marks_reference_only_when_source_is_missing(self):
        documento = Documento.objects.create(
            associado=self.associado,
            tipo=Documento.Tipo.CPF,
            arquivo="uploads/associados/1/inexistente.pdf",
            origem=Documento.Origem.LEGADO_CADASTRO,
        )

        payload = LegacyMediaAssetsService(legacy_root=self.legacy_root).run(
            families=("cadastro",),
            execute=False,
        )

        documento.refresh_from_db()
        self.assertEqual(documento.arquivo.name, "uploads/associados/1/inexistente.pdf")
        self.assertEqual(payload["summary"]["reference_only"], 1)
        self.assertEqual(payload["results"][0]["status"], "reference_only")

    def test_manual_comprovante_already_canonical_is_not_recounted_as_updated(self):
        canonical_path = (
            "pagamentos_mensalidades/comprovantes/2025/12/"
            "12345678900_manual.pdf"
        )
        default_storage.save(canonical_path, ContentFile(b"manual", name="manual.pdf"))

        pagamento_manual = PagamentoMensalidade.objects.create(
            import_uuid="manual-2",
            referencia_month=date(2025, 12, 1),
            cpf_cnpj=self.associado.cpf_cnpj,
            associado=self.associado,
            manual_comprovante_path=canonical_path,
        )

        payload = LegacyMediaAssetsService(legacy_root=self.legacy_root).run(
            families=("manual",),
            execute=False,
        )

        pagamento_manual.refresh_from_db()
        self.assertEqual(pagamento_manual.manual_comprovante_path, canonical_path)
        self.assertEqual(payload["summary"]["already_canonical"], 1)
        self.assertEqual(payload["summary"]["updated"], 0)
        self.assertEqual(payload["results"][0]["status"], "already_canonical")
