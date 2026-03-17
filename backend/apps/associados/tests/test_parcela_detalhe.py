from __future__ import annotations

import tempfile
from datetime import date, datetime
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.associados.models import Associado
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.importacao.models import ArquivoRetorno, ArquivoRetornoItem, PagamentoMensalidade
from apps.refinanciamento.models import Comprovante, Refinanciamento
from apps.tesouraria.models import Pagamento


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ParcelaDetalheEndpointTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")
        cls.agente = User.objects.create_user(
            email="agente.parcelas@abase.local",
            password="Senha@123",
            first_name="Agente",
            last_name="Parcelas",
            is_active=True,
        )
        cls.agente.roles.add(role_agente)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.agente)

    @staticmethod
    def _aware(value: datetime):
        return timezone.make_aware(value)

    def _create_contract(self, *, cpf: str, nome: str) -> Contrato:
        associado = Associado.objects.create(
            nome_completo=nome,
            cpf_cnpj=cpf,
            email=f"{cpf}@teste.local",
            telefone="86999999999",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.agente,
            orgao_publico="SEFAZ",
            matricula_orgao=f"MAT-{cpf[-4:]}",
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.agente,
            valor_bruto=Decimal("1500.00"),
            valor_liquido=Decimal("1200.00"),
            valor_mensalidade=Decimal("500.00"),
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_contrato=date(2026, 1, 10),
            data_aprovacao=date(2026, 1, 10),
            data_primeira_mensalidade=date(2026, 2, 1),
            auxilio_liberado_em=date(2026, 1, 12),
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 4, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("1500.00"),
        )
        Parcela.objects.create(
            ciclo=ciclo,
            numero=1,
            referencia_mes=date(2026, 2, 1),
            valor=Decimal("500.00"),
            data_vencimento=date(2026, 2, 5),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2026, 2, 20),
        )
        Parcela.objects.create(
            ciclo=ciclo,
            numero=2,
            referencia_mes=date(2026, 3, 1),
            valor=Decimal("500.00"),
            data_vencimento=date(2026, 3, 5),
            status=Parcela.Status.NAO_DESCONTADO,
        )
        Parcela.objects.create(
            ciclo=ciclo,
            numero=3,
            referencia_mes=date(2026, 4, 1),
            valor=Decimal("500.00"),
            data_vencimento=date(2026, 4, 5),
            status=Parcela.Status.EM_ABERTO,
        )
        return contrato

    def test_parcela_detalhe_retorna_evidencia_de_arquivo_e_pagamento_inicial(self):
        contrato = self._create_contract(
            cpf="12345678901",
            nome="Associado Arquivo",
        )
        Pagamento.objects.create(
            cadastro=contrato.associado,
            created_by=self.agente,
            contrato_codigo=contrato.codigo,
            contrato_valor_antecipacao=Decimal("1200.00"),
            contrato_margem_disponivel=Decimal("1200.00"),
            cpf_cnpj=contrato.associado.cpf_cnpj,
            full_name=contrato.associado.nome_completo,
            agente_responsavel=contrato.agente.full_name,
            status=Pagamento.Status.PAGO,
            valor_pago=Decimal("1200.00"),
            paid_at=self._aware(datetime(2026, 1, 12, 9, 30)),
            forma_pagamento="pix",
            notes="Efetivação inicial do contrato pela tesouraria.",
        )
        Comprovante.objects.create(
            contrato=contrato,
            ciclo=contrato.ciclos.get(numero=1),
            refinanciamento=None,
            tipo=Comprovante.Tipo.COMPROVANTE_PAGAMENTO_ASSOCIADO,
            papel=Comprovante.Papel.ASSOCIADO,
            arquivo=SimpleUploadedFile("associada.pdf", b"assoc", content_type="application/pdf"),
            enviado_por=self.agente,
            origem=Comprovante.Origem.EFETIVACAO_CONTRATO,
        )
        Comprovante.objects.create(
            contrato=contrato,
            ciclo=contrato.ciclos.get(numero=1),
            refinanciamento=None,
            tipo=Comprovante.Tipo.COMPROVANTE_PAGAMENTO_AGENTE,
            papel=Comprovante.Papel.AGENTE,
            arquivo=SimpleUploadedFile("agente.pdf", b"agente", content_type="application/pdf"),
            enviado_por=self.agente,
            origem=Comprovante.Origem.EFETIVACAO_CONTRATO,
        )

        arquivo_retorno = ArquivoRetorno.objects.create(
            arquivo_nome="retorno-fev.txt",
            arquivo_url="arquivos_retorno/retorno-fev.txt",
            formato=ArquivoRetorno.Formato.TXT,
            orgao_origem="ETIPI/iNETConsig",
            competencia=date(2026, 2, 1),
            uploaded_by=self.agente,
            processado_em=self._aware(datetime(2026, 2, 21, 8, 0)),
            status=ArquivoRetorno.Status.CONCLUIDO,
        )
        parcela = contrato.ciclos.get(numero=1).parcelas.get(numero=1)
        ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo_retorno,
            linha_numero=1,
            cpf_cnpj=contrato.associado.cpf_cnpj,
            matricula_servidor=contrato.associado.matricula_orgao,
            nome_servidor=contrato.associado.nome_completo,
            cargo="Servidor",
            competencia="02/2026",
            valor_descontado=Decimal("500.00"),
            status_codigo="1",
            status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
            status_descricao="Efetivado",
            associado=contrato.associado,
            parcela=parcela,
            processado=True,
            resultado_processamento=ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA,
        )

        response = self.client.get(
            f"/api/v1/associados/{contrato.associado_id}/parcela-detalhe/",
            {
                "contrato_id": contrato.id,
                "referencia_mes": "2026-02-01",
                "kind": "cycle",
            },
        )
        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["cycle_number"], 1)
        self.assertEqual(payload["numero_parcela"], 1)
        self.assertEqual(payload["origem_quitacao"], "arquivo_retorno")
        self.assertEqual(payload["data_importacao_arquivo"], "2026-02-21T08:00:00-03:00")
        self.assertEqual(payload["data_pagamento_tesouraria"], "2026-01-12T09:30:00-03:00")
        self.assertEqual(len(payload["competencia_evidencias"]), 1)
        self.assertEqual(payload["competencia_evidencias"][0]["origem"], "arquivo_retorno")
        self.assertEqual(len(payload["documentos_ciclo"]), 2)
        self.assertIsNone(payload["termo_antecipacao"])

    def test_parcela_detalhe_retorna_relatorio_manual_e_documentos_da_renovacao(self):
        contrato = self._create_contract(
            cpf="98765432100",
            nome="Associado Renovado",
        )
        PagamentoMensalidade.objects.create(
            created_by=self.agente,
            import_uuid="manual-maio",
            referencia_month=date(2026, 5, 1),
            status_code="",
            matricula=contrato.associado.matricula_orgao,
            orgao_pagto="SEFAZ",
            nome_relatorio=contrato.associado.nome_completo,
            cpf_cnpj=contrato.associado.cpf_cnpj,
            associado=contrato.associado,
            valor=Decimal("500.00"),
            manual_status=PagamentoMensalidade.ManualStatus.PAGO,
            manual_paid_at=self._aware(datetime(2026, 5, 6, 11, 15)),
            source_file_path="arquivos_retorno/manual-maio.pdf",
        )
        ArquivoRetorno.objects.create(
            arquivo_nome="mes_retorno_ref_2026-05.pdf",
            arquivo_url="arquivos_retorno/manual/mes_retorno_ref_2026-05.pdf",
            formato=ArquivoRetorno.Formato.MANUAL,
            orgao_origem="Relatório manual",
            competencia=date(2026, 5, 1),
            uploaded_by=self.agente,
            processado_em=self._aware(datetime(2026, 5, 16, 12, 0)),
            status=ArquivoRetorno.Status.CONCLUIDO,
        )

        refinanciamento = Refinanciamento.objects.create(
            associado=contrato.associado,
            contrato_origem=contrato,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 5, 1),
            status=Refinanciamento.Status.EFETIVADO,
            origem=Refinanciamento.Origem.LEGADO,
            legacy_refinanciamento_id=73,
            executado_em=self._aware(datetime(2026, 5, 10, 14, 0)),
            data_ativacao_ciclo=self._aware(datetime(2026, 5, 10, 14, 0)),
            cycle_key="2026-02|2026-03|2026-04",
            ref1=date(2026, 2, 1),
            ref2=date(2026, 3, 1),
            ref3=date(2026, 4, 1),
            cpf_cnpj_snapshot=contrato.associado.cpf_cnpj,
            nome_snapshot=contrato.associado.nome_completo,
            contrato_codigo_origem=contrato.codigo,
            termo_antecipacao_path="refinanciamentos/termo.pdf",
            termo_antecipacao_original_name="termo.pdf",
            termo_antecipacao_uploaded_at=self._aware(datetime(2026, 5, 10, 13, 30)),
        )
        Comprovante.objects.create(
            refinanciamento=refinanciamento,
            contrato=contrato,
            tipo=Comprovante.Tipo.COMPROVANTE_PAGAMENTO_ASSOCIADO,
            papel=Comprovante.Papel.ASSOCIADO,
            arquivo=SimpleUploadedFile("renovacao-associado.pdf", b"assoc", content_type="application/pdf"),
            enviado_por=self.agente,
            origem=Comprovante.Origem.TESOURARIA_RENOVACAO,
        )

        response = self.client.get(
            f"/api/v1/associados/{contrato.associado_id}/parcela-detalhe/",
            {
                "contrato_id": contrato.id,
                "referencia_mes": "2026-05-01",
                "kind": "cycle",
            },
        )
        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["cycle_number"], 2)
        self.assertEqual(payload["origem_quitacao"], "relatorio_competencia")
        self.assertEqual(payload["data_baixa_manual"], "2026-05-06")
        self.assertEqual(payload["data_pagamento_tesouraria"], "2026-05-10T14:00:00-03:00")
        self.assertEqual(payload["competencia_evidencias"][0]["origem"], "relatorio_competencia")
        self.assertEqual(len(payload["documentos_ciclo"]), 1)
        self.assertEqual(payload["documentos_ciclo"][0]["origem"], "tesouraria_renovacao")
        self.assertEqual(payload["termo_antecipacao"]["tipo"], "termo_antecipacao")

    def test_mes_nao_pago_retorna_detalhe_sem_quitacao(self):
        contrato = self._create_contract(
            cpf="55566677788",
            nome="Associado Pendente",
        )
        PagamentoMensalidade.objects.create(
            created_by=self.agente,
            import_uuid="nao-descontado-marco",
            referencia_month=date(2026, 3, 1),
            status_code="2",
            matricula=contrato.associado.matricula_orgao,
            orgao_pagto="SEFAZ",
            nome_relatorio=contrato.associado.nome_completo,
            cpf_cnpj=contrato.associado.cpf_cnpj,
            associado=contrato.associado,
            valor=Decimal("500.00"),
            source_file_path="arquivos_retorno/retorno-marco.txt",
        )

        response = self.client.get(
            f"/api/v1/associados/{contrato.associado_id}/parcela-detalhe/",
            {
                "contrato_id": contrato.id,
                "referencia_mes": "2026-03-01",
                "kind": "unpaid",
            },
        )
        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["kind"], "unpaid")
        self.assertEqual(payload["origem_quitacao"], "pendente")
        self.assertEqual(payload["competencia_evidencias"], [])
