# Deploy da Correção de Aptos a Renovar de Abril e Importação

Data de referência: 10 de abril de 2026

## Objetivo

Aplicar no servidor a mesma correção já validada localmente para:

1. colocar o lote oficial de abril na rota `Aptos a renovar`
2. materializar os cadastros/contratos que só existiam no arquivo retorno
3. permitir exceção controlada para `30/50` apenas no lote oficial de abril
4. impedir que a importação futura volte a fechar ciclos antigos com menos de 3 competências resolvidas
5. zerar o passivo de `ciclo 1` concluído/renovado incompleto

## Escopo fechado desta frente

- CSV oficial usado no reparo:
  - `Controle e Conciliação de Mensalidades_ABASE - RENOVAÇÃO PARCIAL ABRIL.csv`
- Regras entregues:
  - todos os `97` registros do CSV com `abr./26 = PASSIVEL DE RENOVAÇÃO` entram na rota `Aptos a renovar`
  - todos os `188` registros do CSV passam a ter contrato operacional e último ciclo em `apto_a_renovar`
  - `04/2026` fica `em_previsao`
  - `ciclo 1` antigo não pode ficar `ciclo_renovado/fechado` com menos de `3` competências resolvidas
  - contratos `30/50` continuam bloqueados por regra geral
  - exceção: o lote oficial de abril pode receber override persistido para renovação

## Mudanças de código incluídas

### Regras de ciclo e projeção

- [cycle_projection.py](/mnt/d/apps/abasev2/abasev2/backend/apps/contratos/cycle_projection.py)
  - ciclo antigo com renovação efetivada só fica `ciclo_renovado` se tiver `3` competências resolvidas
  - caso contrário, fica `pendencia`
  - isso protege importações futuras contra recriar o erro
- [incomplete_cycle_one_repair.py](/mnt/d/apps/abasev2/abasev2/backend/apps/contratos/incomplete_cycle_one_repair.py)
  - passou a remover do bucket do ciclo as linhas não resolvidas
  - completa `ciclo 1` com referências resolvidas válidas
  - rebaixa para `pendencia` quando não houver base suficiente

### Lote oficial de abril

- [april_renewal_cohort_repair.py](/mnt/d/apps/abasev2/abasev2/backend/apps/contratos/april_renewal_cohort_repair.py)
  - materializa associados/contratos faltantes a partir do retorno
  - relinka itens do retorno
  - força rebuild do lote oficial
  - garante `04/2026` em previsão
  - força sincronização operacional para `apto_a_renovar`
  - habilita override de renovação para `30/50` desse lote
- [repair_april_renewal_cohort.py](/mnt/d/apps/abasev2/abasev2/backend/apps/contratos/management/commands/repair_april_renewal_cohort.py)

### Regra de bloqueio 30/50

- [small_value_rules.py](/mnt/d/apps/abasev2/abasev2/backend/apps/contratos/small_value_rules.py)
  - o bloqueio de renovação para contrato importado `30/50` agora respeita o override persistido
- [small_value_return_materialization.py](/mnt/d/apps/abasev2/abasev2/backend/apps/importacao/small_value_return_materialization.py)
  - usada para materializar os faltantes do lote oficial de abril

### Banco

- Nova migration:
  - [0012_contrato_allow_small_value_renewal.py](/mnt/d/apps/abasev2/abasev2/backend/apps/contratos/migrations/0012_contrato_allow_small_value_renewal.py)
- Novo campo:
  - `Contrato.allow_small_value_renewal`

## Estado validado localmente

### Resultado do lote oficial de abril

Resultado do comando `repair_april_renewal_cohort --apply`:

- `rows_total: 188`
- `rows_with_contract: 188`
- `missing_after_normalization: 0`
- `candidate_contracts_total: 188`
- `touched_contracts_total: 188`
- `small_value_materialized_total: 19`
- `small_value_override_total: 27`
- `final_apto_total: 188`
- `final_april_forecast_total: 188`
- `remaining_incomplete_cycle_one: 0`

### Resultado da conferência da rota

Para o subconjunto do CSV com `abr./26 = PASSIVEL DE RENOVAÇÃO`:

- `passiveis_total: 97`
- `aptos_match: 97`
- `fora_total: 0`

### Resultado do reparo de ciclo 1

Resultado do comando `repair_incomplete_cycle_one --apply` na base atual:

- `candidate_contracts: 89`
- `moved_contracts: 82`
- `downgraded_to_pending: 7`
- `moved_rows: 89`
- `reparcelled_rows: 485`
- `rebuilt_contracts: 82`
- `remaining_invalid_completed_cycle_one: 0`

Auditoria global pós-apply:

- `invalid_cycles: 0`

## Ordem recomendada no servidor

### 1. Backup preventivo

```bash
cd /opt/ABASE/repo
bash deploy/hostinger/scripts/backup_now.sh
```

### 2. Atualizar código

```bash
cd /opt/ABASE/repo
git fetch --all --prune
git pull --ff-only
```

### 3. Garantir que o CSV oficial esteja disponível

Opção A, copiar direto para o container:

```bash
docker cp "Controle e Conciliação de Mensalidades_ABASE - RENOVAÇÃO PARCIAL ABRIL.csv" \
  abase-v2-backend-1:/tmp/abril_passiveis_2026.csv
```

Opção B, copiar para o servidor e depois para o container:

```bash
scp "Controle e Conciliação de Mensalidades_ABASE - RENOVAÇÃO PARCIAL ABRIL.csv" \
  root@SEU_SERVIDOR:/tmp/abril_passiveis_2026.csv

docker cp /tmp/abril_passiveis_2026.csv \
  abase-v2-backend-1:/tmp/abril_passiveis_2026.csv
```

### 4. Rebuild e restart

```bash
docker compose -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  build --no-cache backend frontend celery

docker compose -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  up -d --force-recreate backend frontend celery
```

### 5. Migration

```bash
docker compose -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  exec -T backend python manage.py migrate --noinput
```

### 6. Sanidade do projeto

```bash
docker compose -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  exec -T backend python manage.py check
```

### 7. Reparo de ciclo 1 incompleto

```bash
docker compose -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  exec -T backend python manage.py repair_incomplete_cycle_one \
  --apply \
  --report-json /tmp/repair_incomplete_cycle_one_20260410_server.json
```

### 8. Reparo oficial do lote de abril

```bash
docker compose -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  exec -T backend python manage.py repair_april_renewal_cohort \
  --csv-path /tmp/abril_passiveis_2026.csv \
  --apply \
  --report-json /tmp/repair_april_renewal_cohort_20260410_server.json
```

### 9. Restart final

```bash
docker compose -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  restart backend frontend
```

## Comandos de conferência no servidor

### Conferir o reparo oficial

```bash
docker compose -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  exec -T backend python manage.py shell -c "
import json
from pathlib import Path
path = Path('/tmp/repair_april_renewal_cohort_20260410_server.json')
payload = json.loads(path.read_text(encoding='utf-8'))
print(payload['summary'])
"
```

Esperado:

- `rows_total = 188`
- `rows_with_contract = 188`
- `missing_after_normalization = 0`
- `final_apto_total = 188`
- `remaining_incomplete_cycle_one = 0`

### Conferir os passíveis de abril na rota real

```bash
docker compose -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  exec -T backend python manage.py shell -c "
import csv, re
from pathlib import Path
from apps.contratos.models import Contrato
from apps.contratos.canonicalization import operational_contracts_queryset
from apps.contratos.cycle_projection import build_contract_cycle_projection

csv_path = Path('/tmp/abril_passiveis_2026.csv')
cpfs = []
with csv_path.open('r', encoding='utf-8-sig', newline='') as fh:
    reader = csv.DictReader(fh)
    for row in reader:
        if (row.get('abr./26') or '').strip().upper() == 'PASSIVEL DE RENOVAÇÃO':
            cpfs.append(''.join(re.findall(r'\\d', row.get('CPF', '') or '')).zfill(11))

apt_statuses = {'apto_a_renovar', 'pendente_termo_agente'}
route_cpfs = set()
for contrato in operational_contracts_queryset(
    Contrato.objects.filter(deleted_at__isnull=True).select_related('associado')
):
    projection = build_contract_cycle_projection(contrato)
    if (projection.get('status_renovacao') or '') in apt_statuses:
        route_cpfs.add(contrato.associado.cpf_cnpj)

missing = sorted(set(cpfs) - route_cpfs)
print({'passiveis_total': len(cpfs), 'aptos_match': len(cpfs) - len(missing), 'fora_total': len(missing), 'missing': missing[:20]})
"
```

Esperado:

- `passiveis_total = 97`
- `aptos_match = 97`
- `fora_total = 0`

### Conferir se não restou ciclo antigo concluído incompleto

```bash
docker compose -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  exec -T backend python manage.py shell -c "
from collections import Counter
from apps.contratos.models import Contrato, Ciclo
from apps.contratos.cycle_projection import build_contract_cycle_projection

invalid = []
counter = Counter()
for contrato in Contrato.objects.filter(deleted_at__isnull=True).select_related('associado'):
    projection = build_contract_cycle_projection(contrato)
    cycles = projection.get('cycles', [])
    latest = max((int(item.get('numero') or 0) for item in cycles), default=0)
    for ciclo in cycles:
        numero = int(ciclo.get('numero') or 0)
        status = str(ciclo.get('status') or '')
        resolved = sum(
            1
            for parcela in (ciclo.get('parcelas') or [])
            if str(parcela.get('status') or '') in {'descontado', 'quitada', 'liquidada'}
        )
        if numero < latest and status in {Ciclo.Status.CICLO_RENOVADO, Ciclo.Status.FECHADO} and resolved < 3:
            invalid.append((contrato.id, contrato.codigo, numero, status, resolved))
            counter[status] += 1
print({'invalid_cycles': len(invalid), 'by_status': dict(counter), 'sample': invalid[:10]})
"
```

Esperado:

- `invalid_cycles = 0`

## Resultado funcional esperado no servidor

- todos os `97` passíveis de abril aparecem em `Aptos a renovar`
- os `19` faltantes passam a ter contrato operacional materializado
- o CPF `10529560330` deixa de ficar ausente
- os `30/50` do lote oficial de abril entram na fila por override persistido
- `04/2026` permanece em previsão
- não sobra `ciclo 1` concluído/renovado com menos de `3` resolvidas
- importações futuras não devem recriar o erro estrutural de fechamento indevido do ciclo antigo

## Observações de risco

- o override `allow_small_value_renewal` foi criado para o lote oficial de abril; não é para liberar `30/50` em massa sem critério
- o CSV oficial precisa ser o mesmo usado nesta homologação
- se o servidor estiver com dump diferente da base validada localmente, execute as conferências finais acima antes de homologar visualmente
