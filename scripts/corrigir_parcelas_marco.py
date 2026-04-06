#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aplica correcao em massa nas parcelas de marco/2026 com base no
arquivo retorno Relatorio_D2102-03-2026.txt.

- Parcelas de associados com status 1 (efetivado) -> DESCONTADO
- Parcelas de associados com status 2/3/S (nao descontado) -> NAO_DESCONTADO
- Ciclos NAO sao rebuildados.
- Opera no banco local (abase) que e copia do banco de producao.

Uso:
    cd backend
    python ../scripts/corrigir_parcelas_marco.py
"""

import sys
import os
from pathlib import Path
from datetime import date
from collections import defaultdict

# Setup Django
BACKEND_DIR = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django
django.setup()

from django.db import transaction

from apps.importacao.parsers import ETIPITxtRetornoParser
from apps.contratos.models import Parcela
from apps.associados.models import Associado

# ── Configuracao ─────────────────────────────────────────────────────────────

ARQUIVO_RETORNO = Path(__file__).parent.parent / "backups" / "Relatorio_D2102-03-2026.txt"
REFERENCIA_MES  = date(2026, 3, 1)
DATA_PAGAMENTO  = date(2026, 3, 24)   # data_geracao do arquivo

# Status que significam "descontado"
STATUS_DESCONTADO = {"1"}
# Status que significam "nao descontado"
STATUS_NAO_DESCONTADO = {"2", "3", "4", "5", "6", "S"}

STATUS_DESCRICAO = {
    "1": "Lancado e Efetivado",
    "2": "Nao Lancado por Falta de Margem Temporariamente",
    "3": "Nao Lancado por Outros Motivos",
    "4": "Lancado com Valor Diferente",
    "5": "Nao Lancado por Problemas Tecnicos",
    "6": "Lancamento com Erros",
    "S": "Nao Lancado: Compra de Divida ou Suspensao SEAD",
}


def log(msg):
    print(msg, flush=True)


def parse_arquivo():
    """Usa o parser existente para extrair registros do arquivo."""
    parser = ETIPITxtRetornoParser()
    result = parser.parse(str(ARQUIVO_RETORNO))

    # Agrupa por CPF: se houver duplicata de CPF, usa o ultimo (mesmo comportamento do import)
    by_cpf = {}
    for row in result.rows:
        cpf = "".join(c for c in row.get("cpf", "") if c.isdigit())
        if len(cpf) == 11:
            by_cpf[cpf] = row

    log(f"Arquivo parseado: {len(result.rows)} linhas, {len(by_cpf)} CPFs unicos")
    log(f"  Competencia: {result.competencia}  Data geracao: {result.data_geracao}")
    return by_cpf


def main():
    if not ARQUIVO_RETORNO.exists():
        log(f"ERRO: arquivo nao encontrado em {ARQUIVO_RETORNO}")
        sys.exit(1)

    log(f"Arquivo: {ARQUIVO_RETORNO.name}")
    log(f"Referencia mes: {REFERENCIA_MES}  |  Data pagamento: {DATA_PAGAMENTO}")
    log("-" * 60)

    # 1. Parsear arquivo
    by_cpf = parse_arquivo()

    # 2. Carregar parcelas de marco/2026 do banco local
    parcelas_marco = list(
        Parcela.all_objects.filter(
            referencia_mes=REFERENCIA_MES,
            deleted_at__isnull=True,
        ).exclude(
            status__in=[Parcela.Status.CANCELADO, Parcela.Status.LIQUIDADA]
        ).select_related("ciclo__contrato__associado")
    )
    log(f"Parcelas de marco/2026 no banco local: {len(parcelas_marco)}")

    if not parcelas_marco:
        log("Nenhuma parcela encontrada. Verifique o banco local.")
        sys.exit(0)

    # 3. Indexar parcelas por CPF do associado
    parcelas_por_cpf = defaultdict(list)
    for p in parcelas_marco:
        try:
            assoc = p.ciclo.contrato.associado
            cpf = "".join(c for c in (assoc.cpf_cnpj or "") if c.isdigit())
            if cpf:
                parcelas_por_cpf[cpf].append(p)
        except Exception:
            pass

    log(f"CPFs distintos com parcela em marco: {len(parcelas_por_cpf)}")
    log("-" * 60)

    # 4. Calcular atualizacoes
    para_descontar   = []   # (parcela, novo_status, data_pag, obs)
    para_nao_descontar = []
    sem_match_arquivo = []  # parcela sem CPF no arquivo retorno
    cpf_sem_parcela   = []  # CPF no arquivo sem parcela no banco

    for cpf, row in by_cpf.items():
        status_cod = row.get("status_code", "")
        descricao  = STATUS_DESCRICAO.get(status_cod, status_cod)
        parcelas   = parcelas_por_cpf.get(cpf, [])

        if not parcelas:
            cpf_sem_parcela.append((cpf, row.get("nome", ""), status_cod))
            continue

        for p in parcelas:
            if status_cod in STATUS_DESCONTADO:
                para_descontar.append((p, descricao))
            else:
                para_nao_descontar.append((p, descricao, status_cod))

    for cpf, parcelas in parcelas_por_cpf.items():
        if cpf not in by_cpf:
            sem_match_arquivo.extend(parcelas)

    log(f"Parcelas a marcar DESCONTADO:     {len(para_descontar)}")
    log(f"Parcelas a marcar NAO_DESCONTADO: {len(para_nao_descontar)}")
    log(f"Parcelas SEM registro no arquivo: {len(sem_match_arquivo)}")
    log(f"CPFs no arquivo sem parcela local:{len(cpf_sem_parcela)}")
    log("-" * 60)

    # 5. Mostrar preview antes de confirmar
    if para_nao_descontar:
        log("Amostra NAO_DESCONTADO (primeiros 5):")
        for p, desc, cod in para_nao_descontar[:5]:
            assoc = p.ciclo.contrato.associado
            log(f"  CPF={assoc.cpf_cnpj}  [{cod}] {desc[:50]}")

    if para_descontar:
        log("Amostra DESCONTADO (primeiros 5):")
        for p, desc in para_descontar[:5]:
            assoc = p.ciclo.contrato.associado
            log(f"  CPF={assoc.cpf_cnpj}  {desc}")

    log("-" * 60)
    resposta = input("Confirmar atualizacao? [s/N] ").strip().lower()
    if resposta != "s":
        log("Cancelado.")
        sys.exit(0)

    # 6. Aplicar atualizacoes em massa
    ids_descontar    = []
    ids_nao_descontar_by_obs = defaultdict(list)

    for p, desc in para_descontar:
        ids_descontar.append(p.id)

    for p, desc, cod in para_nao_descontar:
        ids_nao_descontar_by_obs[desc].append(p.id)

    with transaction.atomic():
        # Descontado
        if ids_descontar:
            updated = Parcela.all_objects.filter(id__in=ids_descontar).update(
                status=Parcela.Status.DESCONTADO,
                data_pagamento=DATA_PAGAMENTO,
                observacao="Efetivado - arquivo retorno marco/2026",
            )
            log(f"DESCONTADO: {updated} parcelas atualizadas.")

        # Nao descontado (por grupo de motivo para usar update eficiente)
        total_nd = 0
        for obs, ids in ids_nao_descontar_by_obs.items():
            updated = Parcela.all_objects.filter(id__in=ids).update(
                status=Parcela.Status.NAO_DESCONTADO,
                data_pagamento=None,
                observacao=obs[:255],
            )
            total_nd += updated
        if total_nd:
            log(f"NAO_DESCONTADO: {total_nd} parcelas atualizadas.")

    # 7. Resumo final
    log("-" * 60)
    log("Correcao concluida.")
    log(f"  DESCONTADO aplicado:     {len(ids_descontar)}")
    log(f"  NAO_DESCONTADO aplicado: {sum(len(v) for v in ids_nao_descontar_by_obs.values())}")
    log(f"  Sem match no arquivo:    {len(sem_match_arquivo)}")
    log(f"  CPFs no arquivo s/parc:  {len(cpf_sem_parcela)}")

    if cpf_sem_parcela:
        log("\nCPFs no arquivo SEM parcela local (primeiros 10):")
        for cpf, nome, cod in cpf_sem_parcela[:10]:
            log(f"  {cpf}  [{cod}]  {nome}")

    if sem_match_arquivo:
        log(f"\nParcelas SEM registro no arquivo retorno (primeiros 10):")
        for p in sem_match_arquivo[:10]:
            try:
                assoc = p.ciclo.contrato.associado
                log(f"  CPF={assoc.cpf_cnpj}  parcela_id={p.id}  status_atual={p.status}")
            except Exception:
                log(f"  parcela_id={p.id}  status_atual={p.status}")


if __name__ == "__main__":
    main()
