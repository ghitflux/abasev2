#!/usr/bin/env python3
import os, sys
from pathlib import Path
from datetime import date
from collections import defaultdict

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django; django.setup()

from django.db import transaction
from apps.importacao.parsers import ETIPITxtRetornoParser
from apps.contratos.models import Parcela

ARQUIVO        = Path("/app/backups/Relatorio_D2102-03-2026.txt")
REFERENCIA_MES = date(2026, 3, 1)
DATA_PAGAMENTO = date(2026, 3, 24)
STATUS_DESCONTADO     = {"1"}
STATUS_NAO_DESCONTADO = {"2","3","4","5","6","S"}
STATUS_DESC = {
    "1":"Lancado e Efetivado",
    "2":"Nao Lancado por Falta de Margem Temporariamente",
    "3":"Nao Lancado por Outros Motivos",
    "4":"Lancado com Valor Diferente",
    "5":"Nao Lancado por Problemas Tecnicos",
    "6":"Lancamento com Erros",
    "S":"Nao Lancado: Compra de Divida ou Suspensao SEAD",
}

def log(m): print(m, flush=True)

parser = ETIPITxtRetornoParser()
result = parser.parse(str(ARQUIVO))
by_cpf = {}
for row in result.items:
    cpf = "".join(c for c in str(row.get("cpf_cnpj","")) if c.isdigit())
    if len(cpf)==11: by_cpf[cpf]=row

log(f"Arquivo: {ARQUIVO.name}  competencia={result.meta.competencia}  data={result.meta.data_geracao}")
log(f"{len(result.items)} linhas  |  {len(by_cpf)} CPFs unicos")
from collections import Counter
log(f"Por status: {dict(Counter(r.get('status_codigo','?') for r in by_cpf.values()))}")
log("-"*60)

parcelas = list(
    Parcela.all_objects.filter(referencia_mes=REFERENCIA_MES, deleted_at__isnull=True)
    .exclude(status__in=[Parcela.Status.CANCELADO, Parcela.Status.LIQUIDADA])
    .select_related("ciclo__contrato__associado")
)
log(f"Parcelas marco/2026 no banco: {len(parcelas)}")

parc_por_cpf = defaultdict(list)
for p in parcelas:
    try:
        cpf = "".join(c for c in (p.ciclo.contrato.associado.cpf_cnpj or "") if c.isdigit())
        if cpf: parc_por_cpf[cpf].append(p)
    except: pass

log(f"CPFs distintos com parcela: {len(parc_por_cpf)}")
log("-"*60)

ids_desc=[]; ids_nd=defaultdict(list); cpf_sp=[]; parc_sa=[]

for cpf, row in by_cpf.items():
    cod=row.get("status_codigo",""); obs=STATUS_DESC.get(cod,cod)
    ps=parc_por_cpf.get(cpf,[])
    if not ps: cpf_sp.append((cpf,row.get("nome_servidor",""),cod)); continue
    for p in ps:
        if cod in STATUS_DESCONTADO: ids_desc.append(p.id)
        else: ids_nd[obs[:255]].append(p.id)

for cpf,ps in parc_por_cpf.items():
    if cpf not in by_cpf: parc_sa.extend(ps)

log(f"DESCONTADO:      {len(ids_desc)}")
log(f"NAO_DESCONTADO:  {sum(len(v) for v in ids_nd.values())}")
log(f"Parc sem arquivo:{len(parc_sa)}")
log(f"CPF sem parcela: {len(cpf_sp)}")
log("-"*60)

try: resp=input("Confirmar? [s/N] ").strip().lower()
except EOFError: resp="s"
if resp!="s": log("Cancelado."); sys.exit(0)

with transaction.atomic():
    if ids_desc:
        n=Parcela.all_objects.filter(id__in=ids_desc).update(
            status=Parcela.Status.DESCONTADO, data_pagamento=DATA_PAGAMENTO,
            observacao="Efetivado - retorno marco/2026")
        log(f"DESCONTADO: {n} parcelas")
    total_nd=0
    for obs,ids in ids_nd.items():
        n=Parcela.all_objects.filter(id__in=ids).update(
            status=Parcela.Status.NAO_DESCONTADO, data_pagamento=None, observacao=obs)
        total_nd+=n
    if total_nd: log(f"NAO_DESCONTADO: {total_nd} parcelas")

log("-"*60)
log("Correcao concluida. Ciclos NAO rebuildados.")

from django.db.models import Count
ids_all=ids_desc+[i for ids in ids_nd.values() for i in ids]
if ids_all:
    rows=Parcela.all_objects.filter(id__in=ids_all).values("status").annotate(t=Count("id"))
    log("Resumo: "+str({r["status"]:r["t"] for r in rows}))

if cpf_sp:
    log(f"\nCPFs sem parcela (primeiros 10):")
    for cpf,nome,cod in cpf_sp[:10]: log(f"  {cpf} [{cod}] {nome[:40]}")
