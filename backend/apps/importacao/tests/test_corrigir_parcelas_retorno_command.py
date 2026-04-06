from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import CommandError, call_command

from apps.associados.models import Associado
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.contratos.views import filter_by_status_visual
from apps.importacao.models import ArquivoRetorno
from apps.importacao.tests.base import ImportacaoBaseTestCase


def build_detail_line(
    status: str,
    matricula: str,
    nome: str,
    cargo: str,
    fin: str,
    orgao: str,
    lancamento: str,
    total_pago: str,
    valor: str,
    orgao_pagto: str,
    cpf: str,
) -> str:
    return (
        f"{status:>7}"
        f"{matricula:<10}"
        f"{nome:<31}"
        f"{cargo:<31}"
        f"{fin:>5}"
        f"{orgao:>6}"
        f"{lancamento:>7}"
        f"{total_pago:>12}"
        f"{valor:>13}"
        f"{orgao_pagto:>12}"
        f"{cpf}"
    )


def build_return_file(*lines: str, data_geracao: str = "24/03/2026") -> bytes:
    content = """
Entidade: 2102-ABASE                                                 Referência: 03/2026   Data da Geração: {data_geracao}
STATUS MATRICULA NOME                           CARGO                          FIN. ORGAO LANC.  TOTAL PAGO  VALOR        ORGAO PAGTO CPF
====== ========= ============================== ============================== ==== ============ ===== ===== ============ =========== ===========
{lines}
       Órgão Pagamento:  002-SECRETARIA DE TESTE          -  {count} Lançamento(s)  -  Total R$ 0,00
""".strip().format(
        data_geracao=data_geracao,
        lines="\n".join(lines),
        count=len(lines),
    )
    return content.encode("latin-1")


class CorrigirParcelasRetornoCommandTestCase(ImportacaoBaseTestCase):
    def _create_associado_marco(
        self,
        *,
        cpf: str,
        nome: str,
        parcela_status: str = Parcela.Status.EM_PREVISAO,
        valor: Decimal = Decimal("300.00"),
    ) -> tuple[Associado, Contrato, Parcela]:
        associado = Associado.objects.create(
            nome_completo=nome,
            cpf_cnpj=cpf,
            email=f"{cpf}@teste.local",
            telefone="86999999999",
            orgao_publico="SEDUC",
            matricula_orgao=f"MAT-{cpf[-4:]}",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.tesoureiro,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.tesoureiro,
            codigo=f"CTR-{cpf[-4:]}",
            valor_bruto=Decimal("900.00"),
            valor_liquido=Decimal("900.00"),
            valor_mensalidade=valor,
            prazo_meses=3,
            taxa_antecipacao=Decimal("30.00"),
            margem_disponivel=Decimal("900.00"),
            valor_total_antecipacao=Decimal("900.00"),
            status=Contrato.Status.ATIVO,
            data_contrato=date(2026, 1, 20),
            data_aprovacao=date(2026, 1, 20),
            data_primeira_mensalidade=date(2026, 2, 1),
            auxilio_liberado_em=date(2026, 1, 20),
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 4, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=valor * Decimal("3"),
        )
        Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=1,
            referencia_mes=date(2026, 2, 1),
            valor=valor,
            data_vencimento=date(2026, 2, 5),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2026, 2, 5),
        )
        parcela_marco = Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=2,
            referencia_mes=date(2026, 3, 1),
            valor=valor,
            data_vencimento=date(2026, 3, 5),
            status=parcela_status,
        )
        Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=3,
            referencia_mes=date(2026, 4, 1),
            valor=valor,
            data_vencimento=date(2026, 4, 5),
            status=Parcela.Status.EM_PREVISAO,
        )
        return associado, contrato, parcela_marco

    def _create_duplicate_active_parcela_for_marco(
        self,
        *,
        associado: Associado,
        contrato: Contrato,
        valor: Decimal = Decimal("300.00"),
    ) -> Parcela:
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=2,
            data_inicio=date(2026, 3, 1),
            data_fim=date(2026, 5, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=valor * Decimal("3"),
        )
        return Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=1,
            referencia_mes=date(2026, 3, 1),
            valor=valor,
            data_vencimento=date(2026, 3, 10),
            status=Parcela.Status.EM_ABERTO,
        )

    def _run_command(self, *args: str) -> str:
        stdout = StringIO()
        call_command("corrigir_parcelas_retorno", *args, stdout=stdout)
        return stdout.getvalue()

    def _create_arquivo_retorno_concluido(
        self,
        *,
        nome: str,
        content: bytes,
        competencia: date = date(2026, 3, 1),
    ) -> ArquivoRetorno:
        storage_name = default_storage.save(
            f"arquivos_retorno/{nome}",
            ContentFile(content, name=nome),
        )
        return ArquivoRetorno.objects.create(
            arquivo_nome=nome,
            arquivo_url=storage_name,
            formato=ArquivoRetorno.Formato.TXT,
            orgao_origem="ETIPI/iNETConsig",
            competencia=competencia,
            status=ArquivoRetorno.Status.CONCLUIDO,
            uploaded_by=self.tesoureiro,
        )

    def test_command_dry_run_reports_raw_lines_unique_cpfs_and_duplicate_without_persisting(self):
        _assoc_ok, _contrato_ok, parcela_ok = self._create_associado_marco(
            cpf="11111111111",
            nome="ASSOCIADO DESCONTADO",
        )
        _assoc_ref, _contrato_ref, parcela_ref = self._create_associado_marco(
            cpf="05201186343",
            nome="MARCIANITA MICHELE RAMOS MENDES",
        )
        file_path = default_storage.save(
            "tmp/retorno_marco_dry_run.txt",
            ContentFile(
                build_return_file(
                    build_detail_line(
                        "1",
                        "RET-1001",
                        "ASSOCIADO DESCONTADO",
                        "SERVIDOR",
                        "6580",
                        "002",
                        "001",
                        "300.00",
                        "300.00",
                        "002",
                        "11111111111",
                    ),
                    build_detail_line(
                        "2",
                        "RET-1999",
                        "MARCIANITA MICHELE RAMOS MENDES",
                        "SERVIDOR",
                        "6580",
                        "002",
                        "001",
                        "300.00",
                        "300.00",
                        "002",
                        "05201186343",
                    ),
                    build_detail_line(
                        "2",
                        "RET-1002",
                        "MARCIANITA MICHELE RAMOS MENDES",
                        "SERVIDOR",
                        "6580",
                        "002",
                        "001",
                        "300.00",
                        "300.00",
                        "002",
                        "05201186343",
                    ),
                ),
                name="retorno_marco_dry_run.txt",
            ),
        )
        output = self._run_command(
            "--competencia",
            "2026-03",
            "--arquivo-path",
            default_storage.path(file_path),
        )

        parcela_ok.refresh_from_db()
        parcela_ref.refresh_from_db()

        self.assertIn("modo: dry-run", output)
        self.assertIn("linhas_brutas_total: 3", output)
        self.assertIn("cpfs_unicos_total: 2", output)
        self.assertIn("cpfs_duplicados_total: 1", output)
        self.assertIn("smoke_test: cpf=05201186343 found=true", output)
        self.assertEqual(parcela_ok.status, Parcela.Status.EM_PREVISAO)
        self.assertEqual(parcela_ref.status, Parcela.Status.EM_PREVISAO)

    def test_command_apply_uses_latest_concluded_file_updates_parcelas_marks_review_and_never_rebuilds(self):
        _assoc_paid, contrato_paid, parcela_paid = self._create_associado_marco(
            cpf="11111111111",
            nome="ASSOCIADO DESCONTADO",
        )
        _assoc_ref, contrato_ref, parcela_ref = self._create_associado_marco(
            cpf="05201186343",
            nome="MARCIANITA MICHELE RAMOS MENDES",
        )
        _assoc_missing, _contrato_missing, parcela_missing = self._create_associado_marco(
            cpf="99999999999",
            nome="ASSOCIADO SEM RETORNO",
            parcela_status=Parcela.Status.EM_ABERTO,
            valor=Decimal("150.00"),
        )

        self._create_arquivo_retorno_concluido(
            nome="retorno_marco_antigo.txt",
            content=build_return_file(
                build_detail_line(
                    "1",
                    "RET-1001",
                    "ASSOCIADO DESCONTADO",
                    "SERVIDOR",
                    "6580",
                    "002",
                    "001",
                    "300.00",
                    "300.00",
                    "002",
                    "11111111111",
                ),
                build_detail_line(
                    "1",
                    "RET-1002",
                    "MARCIANITA MICHELE RAMOS MENDES",
                    "SERVIDOR",
                    "6580",
                    "002",
                    "001",
                    "300.00",
                    "300.00",
                    "002",
                    "05201186343",
                ),
            ),
        )
        self._create_arquivo_retorno_concluido(
            nome="retorno_marco_recente.txt",
            content=build_return_file(
                build_detail_line(
                    "1",
                    "RET-1001",
                    "ASSOCIADO DESCONTADO",
                    "SERVIDOR",
                    "6580",
                    "002",
                    "001",
                    "300.00",
                    "300.00",
                    "002",
                    "11111111111",
                ),
                build_detail_line(
                    "2",
                    "RET-1002",
                    "MARCIANITA MICHELE RAMOS MENDES",
                    "SERVIDOR",
                    "6580",
                    "002",
                    "001",
                    "300.00",
                    "300.00",
                    "002",
                    "05201186343",
                ),
            ),
        )

        with patch("apps.contratos.cycle_rebuild.rebuild_contract_cycle_state") as rebuild_mock:
            output = self._run_command("--competencia", "2026-03", "--apply")

        parcela_paid.refresh_from_db()
        parcela_ref.refresh_from_db()
        parcela_missing.refresh_from_db()

        self.assertIn("modo: apply", output)
        self.assertIn("fonte: ArquivoRetorno #", output)
        self.assertIn("parcelas_descontado_total: 1", output)
        self.assertIn("parcelas_descontado_valor: 300.00", output)
        self.assertIn("parcelas_nao_descontado_total: 1", output)
        self.assertIn("parcelas_sem_match_total: 1", output)
        self.assertEqual(parcela_paid.status, Parcela.Status.DESCONTADO)
        self.assertEqual(parcela_paid.data_pagamento, date(2026, 3, 24))
        self.assertIn("ETIPI 1 - Lançado e Efetivado", parcela_paid.observacao)
        self.assertEqual(parcela_ref.status, Parcela.Status.NAO_DESCONTADO)
        self.assertIsNone(parcela_ref.data_pagamento)
        self.assertIn(
            "ETIPI 2 - Não Lançado por Falta de Margem Temporariamente",
            parcela_ref.observacao,
        )
        self.assertEqual(parcela_missing.status, Parcela.Status.EM_ABERTO)
        self.assertIn("parcela sem correspondencia no arquivo", parcela_missing.observacao)
        inadimplentes = filter_by_status_visual(
            Contrato.objects.filter(id__in=[contrato_paid.id, contrato_ref.id]).prefetch_related(
                "ciclos__parcelas"
            ),
            "inadimplente",
        )
        self.assertEqual(list(inadimplentes.values_list("id", flat=True)), [contrato_ref.id])
        rebuild_mock.assert_not_called()

    def test_command_apply_updates_all_active_parcelas_for_same_associado(self):
        associado, contrato, parcela_principal = self._create_associado_marco(
            cpf="33333333333",
            nome="ASSOCIADO DUPLICADO",
        )
        parcela_secundaria = self._create_duplicate_active_parcela_for_marco(
            associado=associado,
            contrato=contrato,
        )
        file_path = default_storage.save(
            "tmp/retorno_marco_dup_parcelas.txt",
            ContentFile(
                build_return_file(
                    build_detail_line(
                        "4",
                        "RET-1003",
                        "ASSOCIADO DUPLICADO",
                        "SERVIDOR",
                        "6580",
                        "002",
                        "001",
                        "300.00",
                        "300.00",
                        "002",
                        "33333333333",
                    )
                ),
                name="retorno_marco_dup_parcelas.txt",
            ),
        )

        self._run_command(
            "--competencia",
            "2026-03",
            "--arquivo-path",
            default_storage.path(file_path),
            "--apply",
        )

        parcela_principal.refresh_from_db()
        parcela_secundaria.refresh_from_db()

        self.assertEqual(parcela_principal.status, Parcela.Status.DESCONTADO)
        self.assertEqual(parcela_secundaria.status, Parcela.Status.DESCONTADO)
        self.assertEqual(parcela_principal.data_pagamento, date(2026, 3, 24))
        self.assertEqual(parcela_secundaria.data_pagamento, date(2026, 3, 24))
        self.assertIn("ETIPI 4 - Lançado com Valor Diferente", parcela_principal.observacao)

    def test_command_aborts_on_duplicate_cpf_with_conflicting_payload(self):
        _assoc_ref, _contrato_ref, _parcela_ref = self._create_associado_marco(
            cpf="05201186343",
            nome="MARCIANITA MICHELE RAMOS MENDES",
        )
        file_path = default_storage.save(
            "tmp/retorno_marco_duplicado_conflitante.txt",
            ContentFile(
                build_return_file(
                    build_detail_line(
                        "1",
                        "RET-1002",
                        "MARCIANITA MICHELE RAMOS MENDES",
                        "SERVIDOR",
                        "6580",
                        "002",
                        "001",
                        "300.00",
                        "300.00",
                        "002",
                        "05201186343",
                    ),
                    build_detail_line(
                        "2",
                        "RET-1002",
                        "MARCIANITA MICHELE RAMOS MENDES",
                        "SERVIDOR",
                        "6580",
                        "002",
                        "001",
                        "300.00",
                        "300.00",
                        "002",
                        "05201186343",
                    ),
                ),
                name="retorno_marco_duplicado_conflitante.txt",
            ),
        )

        with self.assertRaises(CommandError) as ctx:
            self._run_command(
                "--competencia",
                "2026-03",
                "--arquivo-path",
                default_storage.path(file_path),
            )

        self.assertIn("CPF duplicado com payload divergente", str(ctx.exception))
