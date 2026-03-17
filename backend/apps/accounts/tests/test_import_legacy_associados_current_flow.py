from __future__ import annotations

import json
from datetime import date

from django.test import TestCase

from apps.accounts.management.commands.import_legacy_associados_current_flow import (
    Command,
)
from apps.accounts.models import Role, User
from apps.associados.models import Associado, ContatoHistorico, DadosBancarios, Documento, Endereco
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.esteira.models import EsteiraItem, Transicao


def raw_json(value) -> str:
    return "'" + json.dumps(value, ensure_ascii=True).replace("'", "\\'") + "'"


class ImportLegacyAssociadosCurrentFlowCommandTestCase(TestCase):
    def make_command(self) -> Command:
        command = Command()
        command.stdout.write = lambda *_args, **_kwargs: None
        command.stderr.write = lambda *_args, **_kwargs: None
        command._bootstrap_lookup_helpers()
        return command

    def setUp(self):
        super().setUp()
        self.role_admin = Role.objects.create(codigo="ADMIN", nome="Administrador")
        self.role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")

        self.admin = User.objects.create_user(
            email="admin@abase.com",
            password="senha",
            first_name="Admin",
        )
        self.admin.roles.add(self.role_admin)
        self.admin.is_staff = True
        self.admin.is_superuser = True
        self.admin.save(update_fields=["is_staff", "is_superuser", "updated_at"])

        self.agente = User.objects.create_user(
            email="agente@abase.com",
            password="senha",
            first_name="Agente",
            last_name="Padrão",
        )
        self.agente.roles.add(self.role_agente)

    def test_importa_associado_ausente_para_fluxo_atual_com_relacoes(self):
        command = self.make_command()
        row = {
            "id": "99",
            "doc_type": "'CPF'",
            "cpf_cnpj": "'123.456.789-00'",
            "rg": "'998877'",
            "orgao_expedidor": "'SSPPI'",
            "full_name": "'Associado Legado'",
            "birth_date": "'1980-01-02'",
            "profession": "'PROFESSOR'",
            "marital_status": "'Casado(a)'",
            "cep": "'64000-000'",
            "address": "'Rua das Flores'",
            "address_number": "'10'",
            "complement": "'Sala 1'",
            "neighborhood": "'Centro'",
            "city": "'Teresina'",
            "uf": "'pi'",
            "cellphone": "'(86) 99999-9999'",
            "orgao_publico": "'SECRETARIA DA EDUCACAO'",
            "situacao_servidor": "'Ativo'",
            "matricula_servidor_publico": "'ABC123'",
            "email": "'associado@example.com'",
            "bank_name": "'001'",
            "bank_agency": "'1234'",
            "bank_account": "'99999-1'",
            "account_type": "'corrente'",
            "pix_key": "'12345678900'",
            "contrato_mensalidade": "450.00",
            "contrato_prazo_meses": "3",
            "contrato_taxa_antecipacao": "30.00",
            "contrato_margem_disponivel": "945.00",
            "contrato_data_aprovacao": "'2025-08-08'",
            "contrato_data_envio_primeira": "'2025-10-06'",
            "contrato_valor_antecipacao": "1350.00",
            "contrato_status_contrato": "'Concluído'",
            "contrato_mes_averbacao": "'2025-10-01'",
            "contrato_codigo_contrato": "'CTR-LEG-001'",
            "contrato_doacao_associado": "405.00",
            "calc_valor_bruto": "5000.00",
            "calc_liquido_cc": "3502.67",
            "calc_prazo_antecipacao": "3",
            "calc_mensalidade_associativa": "450.00",
            "anticipations_json": raw_json(
                [
                    {
                        "numeroMensalidade": 1,
                        "valorAuxilio": 450,
                        "dataEnvio": "2025-09-25",
                        "status": "Pendente",
                    }
                ]
            ),
            "agente_responsavel": "'Agente Padrao'",
            "agente_filial": "'agentepadrao'",
            "observacoes": "'Importado do legado'",
            "auxilio_taxa": "10.00",
            "auxilio_data_envio": "'2025-08-08'",
            "auxilio_status": "'Pendente'",
            "documents_json": raw_json(
                [
                    {
                        "original_name": "frente.pdf",
                        "stored_name": "frente.pdf",
                        "mime": "application/pdf",
                        "relative_path": "uploads/associados/99/frente.pdf",
                        "uploaded_at": "2025-09-02 03:16:18",
                        "field": "cpf_frente",
                    },
                    {
                        "original_name": "adesao.pdf",
                        "stored_name": "adesao.pdf",
                        "mime": "application/pdf",
                        "relative_path": "uploads/associados/99/adesao.pdf",
                        "uploaded_at": "2025-09-02 03:16:18",
                        "field": "termo_adesao",
                    },
                ]
            ),
            "created_at": "'2025-09-02 03:16:18'",
            "updated_at": "'2025-09-02 03:16:18'",
        }
        summary = {
            "rows_total": 0,
            "associados_created": 0,
            "associados_updated": 0,
            "associados_restored": 0,
            "contratos_created": 0,
            "contratos_restored": 0,
            "ciclos_created": 0,
            "parcelas_created": 0,
            "esteiras_created": 0,
            "transicoes_created": 0,
            "documentos_created": 0,
            "contratos_soft_deleted": 0,
            "ciclos_soft_deleted": 0,
            "parcelas_soft_deleted": 0,
            "competencia_conflicts": 0,
            "rows_skipped": 0,
            "errors": 0,
        }

        command._import_row(row, summary)

        associado = Associado.objects.get(cpf_cnpj="12345678900")
        self.assertEqual(associado.nome_completo, "Associado Legado")
        self.assertEqual(associado.agente_responsavel_id, self.agente.id)
        self.assertEqual(associado.status, Associado.Status.ATIVO)
        self.assertEqual(associado.logradouro, "Rua das Flores")
        self.assertEqual(associado.banco, "001")
        self.assertEqual(associado.orgao_publico, "SECRETARIA DA EDUCACAO")
        self.assertEqual(associado.documents_json[0]["field"], "cpf_frente")

        self.assertFalse(Endereco.objects.filter(associado=associado).exists())
        self.assertFalse(DadosBancarios.objects.filter(associado=associado).exists())
        self.assertFalse(ContatoHistorico.objects.filter(associado=associado).exists())

        contrato = Contrato.objects.get(codigo="CTR-LEG-001")
        self.assertEqual(contrato.associado_id, associado.id)
        self.assertEqual(contrato.status, Contrato.Status.ATIVO)

        ciclo = Ciclo.objects.get(contrato=contrato, numero=1)
        self.assertEqual(ciclo.status, Ciclo.Status.APTO_A_RENOVAR)
        self.assertEqual(Parcela.objects.filter(ciclo=ciclo).count(), 3)

        esteira = EsteiraItem.objects.get(associado=associado)
        self.assertEqual(esteira.etapa_atual, EsteiraItem.Etapa.CONCLUIDO)
        self.assertEqual(esteira.status, EsteiraItem.Situacao.APROVADO)
        self.assertEqual(Transicao.objects.filter(esteira_item=esteira).count(), 1)

        documentos = Documento.objects.filter(associado=associado).order_by("tipo")
        self.assertEqual(documentos.count(), 2)
        self.assertEqual(
            list(documentos.values_list("tipo", flat=True)),
            [Documento.Tipo.DOCUMENTO_FRENTE, Documento.Tipo.TERMO_ADESAO],
        )

    def test_reaproveita_associado_existente_sem_duplicar_esteira_nem_snapshot_atual(self):
        associado = Associado.objects.create(
            cpf_cnpj="71339477300",
            nome_completo="Associado Existente",
            status=Associado.Status.ATIVO,
            email="existente@example.com",
        )
        contrato_atual = Contrato.objects.create(
            associado=associado,
            agente=self.agente,
            codigo="CTR-CUR-001",
            valor_mensalidade="600.00",
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_aprovacao="2026-01-10",
            data_primeira_mensalidade="2026-02-05",
            mes_averbacao="2026-02-01",
        )
        EsteiraItem.objects.create(
            associado=associado,
            etapa_atual=EsteiraItem.Etapa.CONCLUIDO,
            status=EsteiraItem.Situacao.APROVADO,
        )

        command = self.make_command()
        row = {
            "id": "2",
            "doc_type": "'CPF'",
            "cpf_cnpj": "'713.394.773-00'",
            "full_name": "'Associado Existente'",
            "email": "'importado@example.com'",
            "contrato_mensalidade": "300.00",
            "contrato_prazo_meses": "3",
            "contrato_taxa_antecipacao": "30.00",
            "contrato_margem_disponivel": "630.00",
            "contrato_data_aprovacao": "'2025-08-11'",
            "contrato_data_envio_primeira": "'2025-10-06'",
            "contrato_valor_antecipacao": "900.00",
            "contrato_status_contrato": "'Concluído'",
            "contrato_mes_averbacao": "'2025-10-01'",
            "contrato_codigo_contrato": "'CTR-LEG-002'",
            "calc_valor_bruto": "1804.94",
            "calc_liquido_cc": "1804.94",
            "calc_prazo_antecipacao": "3",
            "calc_mensalidade_associativa": "300.00",
            "agente_responsavel": "'Agente Padrao'",
            "agente_filial": "'agentepadrao'",
            "created_at": "'2025-09-02 03:16:18'",
            "updated_at": "'2025-09-02 03:16:18'",
        }
        summary = {
            "rows_total": 0,
            "associados_created": 0,
            "associados_updated": 0,
            "associados_restored": 0,
            "contratos_created": 0,
            "contratos_restored": 0,
            "ciclos_created": 0,
            "parcelas_created": 0,
            "esteiras_created": 0,
            "transicoes_created": 0,
            "documentos_created": 0,
            "contratos_soft_deleted": 0,
            "ciclos_soft_deleted": 0,
            "parcelas_soft_deleted": 0,
            "competencia_conflicts": 0,
            "rows_skipped": 0,
            "errors": 0,
        }

        command._import_row(row, summary)

        associado.refresh_from_db()
        self.assertEqual(Associado.objects.count(), 1)
        self.assertEqual(Contrato.objects.filter(associado=associado).count(), 2)
        self.assertTrue(Contrato.objects.filter(codigo="CTR-CUR-001").exists())
        self.assertTrue(Contrato.objects.filter(codigo="CTR-LEG-002").exists())
        self.assertEqual(EsteiraItem.objects.filter(associado=associado).count(), 1)
        self.assertEqual(Transicao.objects.count(), 0)
        self.assertEqual(associado.contrato_codigo_contrato, contrato_atual.codigo)
        self.assertEqual(associado.email, "existente@example.com")

    def test_documento_legado_importado_com_arquivo_entra_aprovado(self):
        command = self.make_command()
        associado = Associado.objects.create(
            cpf_cnpj="55566677788",
            nome_completo="Associado Documento",
            email="documento@example.com",
        )

        created = command._ensure_documentos(
            associado=associado,
            raw_documents=[
                {
                    "original_name": "frente.pdf",
                    "stored_name": "frente.pdf",
                    "mime": "application/pdf",
                    "relative_path": "uploads/associados/10/frente.pdf",
                    "uploaded_at": "2025-09-02 03:16:18",
                    "field": "cpf_frente",
                }
            ],
            contract_status=Contrato.Status.EM_ANALISE,
            legacy_created_at=None,
            legacy_updated_at=None,
        )

        self.assertEqual(created, 1)
        documento = Documento.objects.get(associado=associado)
        self.assertEqual(documento.status, Documento.Status.APROVADO)

    def test_importa_contrato_mas_pula_agenda_quando_competencia_ja_esta_ocupada(self):
        associado = Associado.objects.create(
            cpf_cnpj="11122233344",
            nome_completo="Associado Com Agenda",
            status=Associado.Status.ATIVO,
            email="agenda@example.com",
        )
        contrato_atual = Contrato.objects.create(
            associado=associado,
            agente=self.agente,
            codigo="CTR-ATUAL-001",
            valor_mensalidade="300.00",
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_aprovacao="2025-08-10",
            data_primeira_mensalidade="2025-10-05",
            mes_averbacao="2025-09-01",
        )
        ciclo_atual = Ciclo.objects.create(
            contrato=contrato_atual,
            numero=1,
            data_inicio=date(2025, 10, 1),
            data_fim=date(2025, 12, 1),
            status=Ciclo.Status.ABERTO,
            valor_total="900.00",
        )
        Parcela.objects.bulk_create(
            [
                Parcela(
                    ciclo=ciclo_atual,
                    numero=1,
                    referencia_mes=date(2025, 10, 1),
                    valor="300.00",
                    data_vencimento=date(2025, 10, 5),
                    status=Parcela.Status.EM_ABERTO,
                ),
                Parcela(
                    ciclo=ciclo_atual,
                    numero=2,
                    referencia_mes=date(2025, 11, 1),
                    valor="300.00",
                    data_vencimento=date(2025, 11, 5),
                    status=Parcela.Status.EM_ABERTO,
                ),
                Parcela(
                    ciclo=ciclo_atual,
                    numero=3,
                    referencia_mes=date(2025, 12, 1),
                    valor="300.00",
                    data_vencimento=date(2025, 12, 5),
                    status=Parcela.Status.EM_ABERTO,
                ),
            ]
        )

        command = self.make_command()
        row = {
            "id": "3",
            "doc_type": "'CPF'",
            "cpf_cnpj": "'111.222.333-44'",
            "full_name": "'Associado Com Agenda'",
            "email": "'agenda-importada@example.com'",
            "contrato_mensalidade": "350.00",
            "contrato_prazo_meses": "3",
            "contrato_taxa_antecipacao": "30.00",
            "contrato_margem_disponivel": "735.00",
            "contrato_data_aprovacao": "'2025-08-11'",
            "contrato_data_envio_primeira": "'2025-10-05'",
            "contrato_valor_antecipacao": "1050.00",
            "contrato_status_contrato": "'Concluído'",
            "contrato_mes_averbacao": "'2025-09-01'",
            "contrato_codigo_contrato": "'CTR-LEG-CONFLITO'",
            "contrato_doacao_associado": "315.00",
            "calc_valor_bruto": "3000.00",
            "calc_liquido_cc": "2500.00",
            "calc_prazo_antecipacao": "3",
            "calc_mensalidade_associativa": "350.00",
            "agente_responsavel": "'Agente Padrao'",
            "agente_filial": "'agentepadrao'",
            "created_at": "'2025-09-02 03:16:18'",
            "updated_at": "'2025-09-02 03:16:18'",
        }
        summary = {
            "rows_total": 0,
            "associados_created": 0,
            "associados_updated": 0,
            "associados_restored": 0,
            "contratos_created": 0,
            "contratos_restored": 0,
            "ciclos_created": 0,
            "parcelas_created": 0,
            "esteiras_created": 0,
            "transicoes_created": 0,
            "documentos_created": 0,
            "contratos_soft_deleted": 0,
            "ciclos_soft_deleted": 0,
            "parcelas_soft_deleted": 0,
            "competencia_conflicts": 0,
            "rows_skipped": 0,
            "errors": 0,
        }

        command._import_row(row, summary)

        contrato_importado = Contrato.objects.get(codigo="CTR-LEG-CONFLITO")
        self.assertEqual(contrato_importado.associado_id, associado.id)
        self.assertFalse(Ciclo.objects.filter(contrato=contrato_importado).exists())
        self.assertEqual(summary["contratos_created"], 1)
        self.assertEqual(summary["ciclos_created"], 0)
        self.assertEqual(summary["parcelas_created"], 0)
        self.assertEqual(summary["competencia_conflicts"], 1)
