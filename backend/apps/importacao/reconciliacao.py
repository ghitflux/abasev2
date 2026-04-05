from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.associados.models import Associado, only_digits
from apps.contratos.competencia import propagate_competencia_status, resolve_processing_competencia_parcela
from apps.contratos.cycle_projection import build_contract_cycle_projection
from apps.contratos.cycle_rebuild import rebuild_contract_cycle_state
from apps.contratos.models import Ciclo, Parcela
from apps.refinanciamento.models import Refinanciamento

from .matching import find_associado
from .models import ArquivoRetorno, ArquivoRetornoItem, ImportacaoLog


def parse_competencia(value: str) -> date:
    return datetime.strptime(value, "%m/%Y").date().replace(day=1)


def add_months(base_date: date, months: int) -> date:
    month_index = base_date.month - 1 + months
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base_date.day, monthrange(year, month)[1])
    return date(year, month, day)


class MotorReconciliacao:
    def __init__(self, arquivo_retorno: ArquivoRetorno):
        self.arquivo_retorno = arquivo_retorno
        self.today = timezone.localdate()

    def reconciliar(self) -> dict[str, int]:
        resumo = {
            "baixa_efetuada": 0,
            "nao_descontado": 0,
            "pendencias_manuais": 0,
            "duplicidades": 0,
            "nao_encontrado": 0,
            "associados_importados": 0,
            "erro": 0,
            "ciclo_aberto": 0,
            "encerramentos": 0,
            "novos_ciclos": 0,
            "efetivados": 0,
            "nao_descontados": 0,
        }

        itens = (
            self.arquivo_retorno.itens.select_related("associado", "parcela")
            .order_by("linha_numero")
        )
        for item in itens:
            if item.processado:
                outcome = self._outcome_from_item(item)
            else:
                outcome = self.reconciliar_item(item)
            resultado = outcome["resultado"]
            if resultado == ArquivoRetornoItem.ResultadoProcessamento.PENDENCIA_MANUAL:
                resumo["pendencias_manuais"] += 1
            elif resultado == ArquivoRetornoItem.ResultadoProcessamento.DUPLICIDADE:
                resumo["duplicidades"] += 1
            else:
                resumo[resultado] += 1
            if outcome["resultado"] == ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA:
                resumo["efetivados"] += 1
            if outcome["resultado"] == ArquivoRetornoItem.ResultadoProcessamento.NAO_DESCONTADO:
                resumo["nao_descontados"] += 1
            if outcome.get("associado_importado"):
                resumo["associados_importados"] += 1
            if outcome["gerou_encerramento"]:
                resumo["encerramentos"] += 1
            if outcome["gerou_novo_ciclo"]:
                resumo["novos_ciclos"] += 1

        return resumo

    def _outcome_from_item(self, item: ArquivoRetornoItem) -> dict[str, object]:
        return {
            "resultado": item.resultado_processamento,
            "gerou_encerramento": item.gerou_encerramento,
            "gerou_novo_ciclo": item.gerou_novo_ciclo,
            "associado_importado": False,
        }

    @transaction.atomic
    def reconciliar_item(self, item: ArquivoRetornoItem) -> dict[str, object]:
        cpf = only_digits(item.cpf_cnpj)
        competencia = parse_competencia(item.competencia)
        associado = item.associado or find_associado(
            cpf=cpf,
            matricula=item.matricula_servidor,
            nome=item.nome_servidor,
            orgao=item.orgao_pagto_nome,
            orgao_alternativo=item.orgao_pagto_codigo,
            orgao_codigo=item.orgao_codigo,
        )
        if not associado:
            item.associado = None
            item.parcela = None
            item.processado = True
            item.resultado_processamento = ArquivoRetornoItem.ResultadoProcessamento.NAO_ENCONTRADO
            item.observacao = "CPF não encontrado no cadastro de associados."
            item.save(
                update_fields=[
                    "associado",
                    "parcela",
                    "processado",
                    "resultado_processamento",
                    "observacao",
                    "updated_at",
                ]
            )
            ImportacaoLog.objects.create(
                arquivo_retorno=self.arquivo_retorno,
                tipo=ImportacaoLog.Tipo.RECONCILIACAO,
                mensagem="CPF não encontrado no cadastro de associados.",
                dados={
                    "linha_numero": item.linha_numero,
                    "cpf_cnpj": cpf,
                    "matricula": item.matricula_servidor,
                    "nome": item.nome_servidor,
                },
            )
            return {
                "resultado": ArquivoRetornoItem.ResultadoProcessamento.NAO_ENCONTRADO,
                "gerou_encerramento": False,
                "gerou_novo_ciclo": False,
                "associado_importado": False,
            }

        parcela = resolve_processing_competencia_parcela(
            associado_id=associado.id,
            referencia_mes=competencia,
            for_update=True,
        )
        if not parcela:
            item.associado = associado
            item.parcela = None
            item.processado = True
            item.resultado_processamento = ArquivoRetornoItem.ResultadoProcessamento.CICLO_ABERTO
            item.observacao = "Nenhuma parcela elegível foi encontrada para a competência."
            item.save(
                update_fields=[
                    "associado",
                    "parcela",
                    "processado",
                    "resultado_processamento",
                    "observacao",
                    "updated_at",
                ]
            )
            ImportacaoLog.objects.create(
                arquivo_retorno=self.arquivo_retorno,
                tipo=ImportacaoLog.Tipo.RECONCILIACAO,
                mensagem="Item sem parcela em aberto para a competência.",
                dados={"linha_numero": item.linha_numero, "cpf_cnpj": cpf},
            )
            return {
                "resultado": ArquivoRetornoItem.ResultadoProcessamento.CICLO_ABERTO,
                "gerou_encerramento": False,
                "gerou_novo_ciclo": False,
                "associado_importado": False,
            }

        item.associado = associado
        item.parcela = parcela
        item.gerou_encerramento = False
        item.gerou_novo_ciclo = False

        if item.status_codigo == "1":
            outcome = self._processar_efetivado(item, parcela)
        elif item.status_codigo == "4":
            outcome = self._processar_efetivado(item, parcela, permitir_diferenca=True)
        elif item.status_codigo in {"2", "3", "S"}:
            outcome = self._processar_rejeitado(item, associado, parcela)
        elif item.status_codigo in {"5", "6"}:
            outcome = self._processar_pendencia_manual(item, parcela)
        else:
            outcome = self._processar_erro(item, f"Status ETIPI desconhecido: {item.status_codigo}")

        item.processado = True
        item.save()
        return {
            **outcome,
            "associado_importado": False,
        }

    def _processar_efetivado(
        self,
        item: ArquivoRetornoItem,
        parcela: Parcela,
        permitir_diferenca: bool = False,
    ) -> dict[str, object]:
        if parcela.status == Parcela.Status.LIQUIDADA:
            item.resultado_processamento = (
                ArquivoRetornoItem.ResultadoProcessamento.PENDENCIA_MANUAL
            )
            item.observacao = (
                "Competência vinculada a contrato liquidado. Revisão manual necessária."
            )
            return {
                "resultado": ArquivoRetornoItem.ResultadoProcessamento.PENDENCIA_MANUAL,
                "gerou_encerramento": False,
                "gerou_novo_ciclo": False,
                "associado_importado": False,
            }

        if item.valor_descontado != parcela.valor and not permitir_diferenca:
            item.resultado_processamento = ArquivoRetornoItem.ResultadoProcessamento.PENDENCIA_MANUAL
            item.observacao = (
                "Divergência de valor entre arquivo retorno e parcela. Revisão manual necessária."
            )
            ImportacaoLog.objects.create(
                arquivo_retorno=self.arquivo_retorno,
                tipo=ImportacaoLog.Tipo.RECONCILIACAO,
                mensagem="Divergência de valor detectada.",
                dados={
                    "linha_numero": item.linha_numero,
                    "valor_arquivo": str(item.valor_descontado),
                    "valor_parcela": str(parcela.valor),
                },
            )
            return {
                "resultado": ArquivoRetornoItem.ResultadoProcessamento.PENDENCIA_MANUAL,
                "gerou_encerramento": False,
                "gerou_novo_ciclo": False,
                "associado_importado": False,
            }

        if parcela.status != Parcela.Status.DESCONTADO:
            parcela.status = Parcela.Status.DESCONTADO
            if not parcela.data_pagamento:
                parcela.data_pagamento = self.today
            nota = f"Baixa automática via arquivo retorno {self.arquivo_retorno.arquivo_nome}."
            if permitir_diferenca and item.valor_descontado != parcela.valor:
                nota = (
                    f"{nota} Valor do arquivo: {item.valor_descontado}. "
                    f"Valor da parcela: {parcela.valor}."
                )
            parcela.observacao = self._append_note(parcela.observacao, nota)
            parcela.save(update_fields=["status", "data_pagamento", "observacao", "updated_at"])
            propagate_competencia_status(parcela)

        item.resultado_processamento = ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA
        if permitir_diferenca:
            item.observacao = "Parcela baixada automaticamente com divergência sinalizada pelo retorno."
        else:
            item.observacao = "Parcela baixada automaticamente."

        rebuild_contract_cycle_state(parcela.ciclo.contrato, execute=True)
        parcela.ciclo.contrato.refresh_from_db()
        projection = build_contract_cycle_projection(parcela.ciclo.contrato)
        post_result = self._pos_processar_ciclo(parcela.ciclo)
        item.gerou_encerramento = post_result["gerou_encerramento"]
        item.gerou_novo_ciclo = (
            projection["status_renovacao"] == Refinanciamento.Status.APTO_A_RENOVAR
        )

        return {
            "resultado": ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA,
            "gerou_novo_ciclo": item.gerou_novo_ciclo,
            **post_result,
            "associado_importado": False,
        }

    def _processar_rejeitado(
        self,
        item: ArquivoRetornoItem,
        associado: Associado,
        parcela: Parcela,
    ) -> dict[str, object]:
        if parcela.status != Parcela.Status.NAO_DESCONTADO:
            parcela.status = Parcela.Status.NAO_DESCONTADO
            parcela.observacao = self._append_note(parcela.observacao, item.status_descricao)
            parcela.save(update_fields=["status", "observacao", "updated_at"])
            propagate_competencia_status(parcela)

        if associado.status != Associado.Status.INADIMPLENTE:
            associado.status = Associado.Status.INADIMPLENTE
            associado.observacao = self._append_note(associado.observacao, item.status_descricao)
            associado.save(update_fields=["status", "observacao", "updated_at"])
        rebuild_contract_cycle_state(parcela.ciclo.contrato, execute=True)

        item.motivo_rejeicao = item.status_descricao
        item.resultado_processamento = ArquivoRetornoItem.ResultadoProcessamento.NAO_DESCONTADO
        item.observacao = item.status_descricao
        return {
            "resultado": ArquivoRetornoItem.ResultadoProcessamento.NAO_DESCONTADO,
            "gerou_encerramento": False,
            "gerou_novo_ciclo": False,
            "associado_importado": False,
        }

    def _processar_pendencia_manual(
        self, item: ArquivoRetornoItem, parcela: Parcela
    ) -> dict[str, object]:
        item.resultado_processamento = ArquivoRetornoItem.ResultadoProcessamento.PENDENCIA_MANUAL
        item.observacao = item.status_descricao
        ImportacaoLog.objects.create(
            arquivo_retorno=self.arquivo_retorno,
            tipo=ImportacaoLog.Tipo.RECONCILIACAO,
            mensagem="Pendência manual criada pelo arquivo retorno.",
            dados={"linha_numero": item.linha_numero, "status_codigo": item.status_codigo},
        )
        return {
            "resultado": ArquivoRetornoItem.ResultadoProcessamento.PENDENCIA_MANUAL,
            "gerou_encerramento": False,
            "gerou_novo_ciclo": False,
            "associado_importado": False,
        }

    def _processar_erro(
        self, item: ArquivoRetornoItem, mensagem: str
    ) -> dict[str, object]:
        item.resultado_processamento = ArquivoRetornoItem.ResultadoProcessamento.ERRO
        item.observacao = mensagem
        ImportacaoLog.objects.create(
            arquivo_retorno=self.arquivo_retorno,
            tipo=ImportacaoLog.Tipo.ERRO,
            mensagem=mensagem,
            dados={"linha_numero": item.linha_numero},
        )
        return {
            "resultado": ArquivoRetornoItem.ResultadoProcessamento.ERRO,
            "gerou_encerramento": False,
            "gerou_novo_ciclo": False,
            "associado_importado": False,
        }

    def _pos_processar_ciclo(self, ciclo: Ciclo) -> dict[str, bool]:
        return {
            "gerou_encerramento": False,
            "gerou_novo_ciclo": False,
        }

    @staticmethod
    def _append_note(base: str, note: str) -> str:
        if not base:
            return note
        if note in base:
            return base
        return f"{base}\n{note}"
