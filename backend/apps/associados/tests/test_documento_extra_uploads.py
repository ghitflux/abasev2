import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.associados.models import Associado, Documento


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class DocumentoExtraUploadsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")
        cls.agente = User.objects.create_user(
            email="agente.documentos@teste.local",
            password="Senha@123",
            first_name="Agente",
            last_name="Uploads",
            is_active=True,
        )
        cls.agente.roles.add(role_agente)
        cls.associado = Associado.objects.create(
            nome_completo="Associado Documentos Extras",
            cpf_cnpj="12345678903",
            email="documentos@teste.local",
            telefone="86999999999",
            orgao_publico="SEFAZ",
            agente_responsavel=cls.agente,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.agente)

    def test_agente_pode_subir_dois_anexos_extras_com_tipos_distintos(self):
        response1 = self.client.post(
            f"/api/v1/associados/{self.associado.id}/documentos/",
            {
                "tipo": Documento.Tipo.ANEXO_EXTRA_1,
                "arquivo": SimpleUploadedFile(
                    "extra-1.pdf",
                    b"conteudo-1",
                    content_type="application/pdf",
                ),
            },
        )
        response2 = self.client.post(
            f"/api/v1/associados/{self.associado.id}/documentos/",
            {
                "tipo": Documento.Tipo.ANEXO_EXTRA_2,
                "arquivo": SimpleUploadedFile(
                    "extra-2.pdf",
                    b"conteudo-2",
                    content_type="application/pdf",
                ),
            },
        )

        self.assertEqual(response1.status_code, 201, response1.json())
        self.assertEqual(response2.status_code, 201, response2.json())
        self.assertEqual(
            Documento.objects.filter(
                associado=self.associado,
                tipo__in=[Documento.Tipo.ANEXO_EXTRA_1, Documento.Tipo.ANEXO_EXTRA_2],
            ).count(),
            2,
        )
