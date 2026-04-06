from __future__ import annotations

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import Role, User, UserRole
from apps.associados.models import Associado, Documento
from apps.associados.serializers import AssociadoDetailSerializer
from apps.esteira.models import DocIssue, EsteiraItem


class DocumentoStatusBackfillTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.analista = User.objects.create_user(
            email="analista.docs@abase.local",
            password="Senha@123",
            first_name="Analista",
            last_name="Docs",
            is_active=True,
        )

    def _create_associado(self, *, cpf: str, matricula_orgao: str = "") -> Associado:
        return Associado.objects.create(
            nome_completo=f"Associado {cpf[-4:]}",
            cpf_cnpj=cpf,
            matricula_orgao=matricula_orgao,
            email=f"{cpf}@teste.local",
        )

    def test_associado_detail_serializer_expoe_matricula_display(self):
        associado = self._create_associado(
            cpf="12345678901",
            matricula_orgao="000123",
        )

        payload = AssociadoDetailSerializer(associado).data

        self.assertEqual(payload["matricula_display"], "000123")
        self.assertEqual(payload["matricula"], associado.matricula)
        self.assertEqual(payload["origem_cadastro_slug"], "web")
        self.assertEqual(payload["origem_cadastro_label"], "Web")

    def test_associado_detail_serializer_oculta_contrato_sombra(self):
        associado = self._create_associado(cpf="12345678909")
        contrato_canonico = associado.contratos.model.objects.create(
            associado=associado,
            codigo="CTR-TESTE-0001",
            valor_bruto="900.00",
            valor_liquido="900.00",
            valor_mensalidade="300.00",
            prazo_meses=3,
            status="ativo",
        )
        associado.contratos.model.objects.create(
            associado=associado,
            codigo="RETIMP-202604-TESTE",
            valor_bruto="900.00",
            valor_liquido="900.00",
            valor_mensalidade="300.00",
            prazo_meses=3,
            status="ativo",
            contrato_canonico=contrato_canonico,
            tipo_unificacao="retimp_shadow",
        )

        payload = AssociadoDetailSerializer(associado).data

        self.assertEqual(len(payload["contratos"]), 1)
        self.assertEqual(payload["contratos"][0]["id"], contrato_canonico.id)

    def test_associado_detail_serializer_expoe_origem_mobile(self):
        role_mobile = Role.objects.create(codigo="ASSOCIADODOIS", nome="Associado 2")
        user = User.objects.create_user(
            email="mobile.associado@abase.local",
            password="Senha@123",
            first_name="Mobile",
            last_name="Associado",
            is_active=True,
        )
        UserRole.objects.create(user=user, role=role_mobile)
        associado = self._create_associado(cpf="12312312312")
        associado.user = user
        associado.save(update_fields=["user", "updated_at"])

        payload = AssociadoDetailSerializer(associado).data

        self.assertEqual(payload["origem_cadastro_slug"], "mobile")
        self.assertEqual(payload["origem_cadastro_label"], "Mobile")

    def test_backfill_aprova_documento_legado_sem_pendencia(self):
        associado = self._create_associado(cpf="98765432100")
        documento = Documento.objects.create(
            associado=associado,
            tipo=Documento.Tipo.CONTRACHEQUE,
            arquivo="documentos/associados/98765432100/contracheque/teste.pdf",
            origem=Documento.Origem.LEGADO_CADASTRO,
            status=Documento.Status.PENDENTE,
        )

        call_command("backfill_legacy_document_statuses", "--execute")

        documento.refresh_from_db()
        associado.refresh_from_db()
        self.assertEqual(documento.status, Documento.Status.APROVADO)
        self.assertEqual(associado.documents_json[0]["status"], Documento.Status.APROVADO)

    def test_backfill_preserva_documento_com_doc_issue_aberta(self):
        associado = self._create_associado(cpf="11122233344")
        Documento.objects.create(
            associado=associado,
            tipo=Documento.Tipo.DOCUMENTO_FRENTE,
            arquivo="documentos/associados/11122233344/documento_frente/teste.pdf",
            origem=Documento.Origem.LEGADO_CADASTRO,
            status=Documento.Status.PENDENTE,
        )
        EsteiraItem.objects.create(associado=associado)
        DocIssue.objects.create(
            associado=associado,
            cpf_cnpj=associado.cpf_cnpj,
            analista=self.analista,
            mensagem="Documento precisa de revisão.",
            status=DocIssue.Status.INCOMPLETO,
        )

        call_command("backfill_legacy_document_statuses", "--execute")

        self.assertEqual(
            associado.documentos.get(tipo=Documento.Tipo.DOCUMENTO_FRENTE).status,
            Documento.Status.PENDENTE,
        )
