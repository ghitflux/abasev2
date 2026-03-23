from __future__ import annotations

import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.associados.models import Associado
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.importacao.models import ArquivoRetorno


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ImportacaoBaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role_admin = Role.objects.create(codigo="ADMIN", nome="Administrador")
        cls.role_coord = Role.objects.create(codigo="COORDENADOR", nome="Coordenador")
        cls.role_tes = Role.objects.create(codigo="TESOUREIRO", nome="Tesoureiro")
        cls.role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")
        cls.admin = cls._create_user("admin@abase.local", cls.role_admin, "Admin")
        cls.coordenador = cls._create_user(
            "coord@abase.local", cls.role_coord, "Coordenador"
        )
        cls.tesoureiro = cls._create_user("tes@abase.local", cls.role_tes, "Tes")
        cls.agente = cls._create_user("agente@abase.local", cls.role_agente, "Agente")

    @classmethod
    def _create_user(cls, email: str, role: Role, first_name: str) -> User:
        user = User.objects.create_user(
            email=email,
            password="Senha@123",
            first_name=first_name,
            last_name="ABASE",
            is_active=True,
        )
        user.roles.add(role)
        return user

    def setUp(self):
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)

        self.coord_client = APIClient()
        self.coord_client.force_authenticate(self.coordenador)

        self.tes_client = APIClient()
        self.tes_client.force_authenticate(self.tesoureiro)

        self.agent_client = APIClient()
        self.agent_client.force_authenticate(self.agente)

    def fixture_path(self, name: str = "retorno_etipi_052025.txt") -> Path:
        return Path(__file__).resolve().parent / "fixtures" / name

    def fixture_bytes(self, name: str = "retorno_etipi_052025.txt") -> bytes:
        return self.fixture_path(name).read_bytes()

    def create_associado_com_contrato(
        self,
        *,
        cpf: str,
        nome: str,
        valor_mensalidade: Decimal = Decimal("30.00"),
        competencia_final: date = date(2025, 5, 1),
        status_ultima_parcela: str = Parcela.Status.EM_ABERTO,
        matricula_orgao: str = "",
        orgao_publico: str = "Órgão Teste",
    ) -> tuple[Associado, Contrato, Ciclo]:
        associado = Associado.objects.create(
            nome_completo=nome,
            cpf_cnpj=cpf,
            email=f"{cpf}@teste.local",
            telefone="86999999999",
            orgao_publico=orgao_publico,
            matricula_orgao=matricula_orgao,
            status=Associado.Status.ATIVO,
            agente_responsavel=self.tesoureiro,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.tesoureiro,
            valor_bruto=Decimal("90.00"),
            valor_liquido=Decimal("90.00"),
            valor_mensalidade=valor_mensalidade,
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_primeira_mensalidade=date(2025, 3, 1),
            data_aprovacao=date(2025, 2, 20),
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2025, 3, 1),
            data_fim=competencia_final,
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("90.00"),
        )
        Parcela.objects.bulk_create(
            [
                Parcela(
                    ciclo=ciclo,
                    numero=1,
                    referencia_mes=date(2025, 3, 1),
                    valor=valor_mensalidade,
                    data_vencimento=date(2025, 3, 1),
                    status=Parcela.Status.DESCONTADO,
                    data_pagamento=date(2025, 3, 15),
                ),
                Parcela(
                    ciclo=ciclo,
                    numero=2,
                    referencia_mes=date(2025, 4, 1),
                    valor=valor_mensalidade,
                    data_vencimento=date(2025, 4, 1),
                    status=Parcela.Status.DESCONTADO,
                    data_pagamento=date(2025, 4, 15),
                ),
                Parcela(
                    ciclo=ciclo,
                    numero=3,
                    referencia_mes=competencia_final,
                    valor=valor_mensalidade,
                    data_vencimento=competencia_final,
                    status=status_ultima_parcela,
                ),
            ]
        )
        return associado, contrato, ciclo

    def create_arquivo_retorno(self, *, nome: str = "retorno.txt") -> ArquivoRetorno:
        return ArquivoRetorno.objects.create(
            arquivo_nome=nome,
            arquivo_url=f"arquivos_retorno/{nome}",
            formato=ArquivoRetorno.Formato.TXT,
            orgao_origem="ETIPI/iNETConsig",
            competencia=date(2025, 5, 1),
            uploaded_by=self.tesoureiro,
        )

    def release_cycle_competencia_locks(self, cycle: Ciclo) -> None:
        Parcela.all_objects.filter(ciclo=cycle).update(competencia_lock=None)
