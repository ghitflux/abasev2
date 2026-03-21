from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.contratos.cycle_rebuild import rebuild_contract_cycle_state, relink_contract_documents
from apps.contratos.models import Contrato
from apps.importacao.manual_return_conflicts import (
    competencia_item_label,
    promote_pagamento_to_return,
    should_promote_manual_pagamento_to_return,
)
from apps.importacao.models import ArquivoRetorno, ArquivoRetornoItem, PagamentoMensalidade
from apps.importacao.reconciliacao import MotorReconciliacao


def _parse_competencia(value: str | None):
    if not value:
        raise CommandError("Competência obrigatória. Use --competencia YYYY-MM.")
    try:
        return datetime.strptime(value, "%Y-%m").date().replace(day=1)
    except ValueError as exc:
        raise CommandError("Competência inválida. Use YYYY-MM.") from exc


class Command(BaseCommand):
    help = (
        "Audita e repara competências marcadas como manuais, mas que já constam "
        "como efetivadas no arquivo retorno."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--competencia",
            required=True,
            help="Competência no formato YYYY-MM.",
        )
        parser.add_argument(
            "--cpf",
            help="CPF para execução pontual.",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Persiste as alterações. Sem isso, executa em dry-run.",
        )

    def handle(self, *args, **options):
        competencia = _parse_competencia(options["competencia"])
        cpf = "".join(char for char in (options.get("cpf") or "") if char.isdigit())
        competencia_item = competencia_item_label(competencia)
        pagamentos = (
            PagamentoMensalidade.objects.select_related("associado")
            .filter(
                referencia_month=competencia,
                manual_status=PagamentoMensalidade.ManualStatus.PAGO,
            )
            .order_by("cpf_cnpj", "id")
        )
        if cpf:
            pagamentos = pagamentos.filter(cpf_cnpj=cpf)

        stats = Counter()
        contract_ids: set[int] = set()
        item_ids_to_reprocess: set[int] = set()
        arquivo_ids_to_refresh: set[int] = set()
        impacted_cpfs: set[str] = set()
        examples: list[dict[str, object]] = []

        with transaction.atomic():
            for pagamento in pagamentos.iterator():
                stats["pagamentos_auditados"] += 1
                items = list(
                    ArquivoRetornoItem.objects.select_related("arquivo_retorno")
                    .filter(
                        cpf_cnpj=pagamento.cpf_cnpj,
                        competencia=competencia_item,
                    )
                    .order_by("arquivo_retorno_id", "linha_numero", "id")
                )
                if not items:
                    stats["sem_item_retorno"] += 1
                    continue

                effective_matches = [
                    item
                    for item in items
                    if should_promote_manual_pagamento_to_return(
                        pagamento,
                        return_status_code=item.status_codigo,
                        return_valor=Decimal(str(item.valor_descontado))
                        if item.valor_descontado is not None
                        else None,
                    )
                ]
                if effective_matches:
                    stats["com_item_efetivado"] += 1
                    if options["execute"]:
                        update_fields = promote_pagamento_to_return(
                            pagamento,
                            return_item=effective_matches[0],
                            source_file_path=effective_matches[0].arquivo_retorno.arquivo_url,
                            import_uuid=pagamento.import_uuid,
                        )
                        if update_fields:
                            pagamento.save(update_fields=[*sorted(set(update_fields)), "updated_at"])
                    stats["convertidos"] += 1
                    impacted_cpfs.add(pagamento.cpf_cnpj)
                    if pagamento.associado_id:
                        contract_ids.update(
                            Contrato.objects.filter(associado_id=pagamento.associado_id).values_list(
                                "id", flat=True
                            )
                        )
                    for item in effective_matches:
                        item_ids_to_reprocess.add(item.id)
                        arquivo_ids_to_refresh.add(item.arquivo_retorno_id)
                    if len(examples) < 20:
                        examples.append(
                            {
                                "cpf_cnpj": pagamento.cpf_cnpj,
                                "pagamento_id": pagamento.id,
                                "return_item_ids": [item.id for item in effective_matches],
                            }
                        )
                    continue

                if any(item.status_codigo in {"2", "3", "S"} for item in items):
                    stats["retorno_rejeitado"] += 1
                else:
                    stats["divergencia_valor_ou_status"] += 1

            if options["execute"]:
                for contrato in (
                    Contrato.objects.select_related("associado")
                    .filter(id__in=sorted(contract_ids))
                    .order_by("id")
                ):
                    rebuild_contract_cycle_state(contrato, execute=True)
                if contract_ids:
                    relink_contract_documents(contract_ids)

                items_by_arquivo: dict[int, list[int]] = defaultdict(list)
                for item_id, arquivo_id in (
                    ArquivoRetornoItem.objects.filter(id__in=sorted(item_ids_to_reprocess))
                    .values_list("id", "arquivo_retorno_id")
                ):
                    items_by_arquivo[arquivo_id].append(item_id)

                for arquivo_id, item_ids in items_by_arquivo.items():
                    arquivo = ArquivoRetorno.objects.get(id=arquivo_id)
                    motor = MotorReconciliacao(arquivo)
                    for item in ArquivoRetornoItem.objects.filter(id__in=item_ids).order_by(
                        "linha_numero", "id"
                    ):
                        motor.reconciliar_item(item)
                    resumo = motor.reconciliar()
                    payload = dict(arquivo.resultado_resumo or {})
                    for key, value in resumo.items():
                        payload[key] = value
                    arquivo.resultado_resumo = payload
                    arquivo.processados = arquivo.itens.filter(processado=True).count()
                    arquivo.nao_encontrados = resumo["nao_encontrado"]
                    arquivo.save(
                        update_fields=[
                            "resultado_resumo",
                            "processados",
                            "nao_encontrados",
                            "updated_at",
                        ]
                    )
                stats["contratos_rebuildados"] = len(contract_ids)
                stats["itens_reprocessados"] = len(item_ids_to_reprocess)
                stats["arquivos_atualizados"] = len(arquivo_ids_to_refresh)
            else:
                transaction.set_rollback(True)

        mode = "execute" if options["execute"] else "dry-run"
        self.summary = {
            "mode": mode,
            "competencia": competencia.strftime("%Y-%m"),
            "cpf": cpf or None,
            "stats": dict(stats),
            "impacted_cpfs": sorted(impacted_cpfs),
            "examples": examples,
        }

        self.stdout.write(f"modo: {mode}")
        self.stdout.write(f"competencia: {competencia.strftime('%Y-%m')}")
        if cpf:
            self.stdout.write(f"cpf: {cpf}")
        for key in sorted(stats):
            self.stdout.write(f"{key}: {stats[key]}")
        if impacted_cpfs:
            self.stdout.write(f"cpfs impactados: {', '.join(sorted(impacted_cpfs))}")
