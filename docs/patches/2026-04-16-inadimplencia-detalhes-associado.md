# Patch 2026-04-16: Inadimplentes e Detalhe do Associado

## Problema

Dois comportamentos estavam divergentes:

1. A rota de `Tesouraria > Inadimplentes` não carregava todas as parcelas atrasadas dos associados.
2. Na visualização de ciclos do associado, a seção de parcelas em atraso não separava corretamente o que ainda está inadimplente do que já foi quitado fora do ciclo.

## Causa raiz

### 1. Fila de inadimplentes

No serviço `BaixaManualService.listar_parcelas_pendentes`, qualquer existência de arquivos de retorno concluídos fazia o backend ignorar todas as parcelas materializadas com status `nao_descontado`, mesmo quando aquela parcela não tinha item correspondente no retorno mais recente.

Na prática, isso removia da fila parcelas antigas e vencidas que continuavam inadimplentes no contrato.

Arquivo corrigido:

- `backend/apps/tesouraria/services.py`

### 2. Detalhe do associado

Na tela `Associados`, o painel de ciclos mostrava todos os registros de `meses_nao_pagos` dentro da mesma aba `Parcelas não descontadas`, inclusive competências já regularizadas fora do ciclo (`quitada`, `descontado`, `liquidada`).

Isso tornava a leitura confusa e passava a impressão de que as parcelas realmente inadimplentes não estavam sendo exibidas corretamente.

Arquivo corrigido:

- `apps/web/src/app/(dashboard)/associados/page.tsx`

## O que foi alterado

### Backend

- removido o descarte indevido de parcelas `nao_descontado` materializadas quando existiam arquivos de retorno recentes;
- mantida apenas a deduplicação correta por:
  - `parcela_id`
  - `associado_id + referencia_mes`

Isso permite que a rota de inadimplentes continue preferindo o item do retorno quando ele existe, sem perder a parcela materializada quando o retorno não cobre aquele caso.

### Frontend

No painel de ciclos do associado:

- a aba `Parcelas não descontadas` agora mostra apenas registros realmente em aberto;
- foi criada a aba `Quitadas fora do ciclo` para competências regularizadas (`quitada`, `descontado`, `liquidada`);
- o total exibido em cada aba passa a refletir somente o respectivo subconjunto.

## Teste adicionado

Arquivo:

- `backend/apps/tesouraria/tests/test_baixa_manual.py`

Cobertura nova:

- garante que uma parcela `nao_descontado` materializada continue aparecendo na fila mesmo quando existe arquivo de retorno mais recente para outra competência/caso.

## Validação local realizada

### Backend

Comando de auditoria manual:

```bash
docker compose exec -T backend python manage.py shell -c "
from apps.tesouraria.services import BaixaManualService
rows = BaixaManualService.listar_parcelas_pendentes(status_filter='nao_descontado')
print('rows', len(rows))
print(any(r['contrato_codigo']=='CTR-20250922180826-LYSY3' and str(r['referencia_mes'])=='2025-10-01' for r in rows))
"
```

Resultado esperado/validado:

- `rows 591`
- `True` para o contrato de exemplo `CTR-20250922180826-LYSY3` na competência `2025-10-01`

Também foi validada a projeção de detalhe:

```bash
docker compose exec -T backend python manage.py shell -c "
from apps.contratos.models import Contrato
from apps.contratos.cycle_projection import build_contract_cycle_projection
c = Contrato.objects.get(codigo='CTR-20250922180826-LYSY3')
p = build_contract_cycle_projection(c)
print({
    'unresolved': [
        (str(i['referencia_mes']), i['status'])
        for i in p['unpaid_months']
        if i['status'] not in ['quitada', 'descontado', 'liquidada']
    ],
    'regularized': [
        (str(i['referencia_mes']), i['status'])
        for i in p['unpaid_months']
        if i['status'] in ['quitada', 'descontado', 'liquidada']
    ],
})
"
```

Resultado esperado/validado:

- `unresolved` contendo `('2025-10-01', 'nao_descontado')`

### Limitação conhecida da suíte automatizada

O teste Django focado não pôde ser executado integralmente no container local porque o banco de teste `test_abase_v2` já existe no MySQL do ambiente:

- erro: `Can't create database 'test_abase_v2'; database exists`

## Deploy

```bash
cd /app
git pull
docker compose build backend web
docker compose up -d backend web
```

## Script pós-deploy

Arquivo:

- `scripts/post_deploy_inadimplencia_audit.sh`

Executar:

```bash
bash scripts/post_deploy_inadimplencia_audit.sh
```

## Verificação pós-deploy

### 1. Auditoria técnica

Rodar:

```bash
bash scripts/post_deploy_inadimplencia_audit.sh
```

Esperado:

- `parcelas_materializadas_sem_fila=0`

### 2. Verificação manual da rota Inadimplentes

Abrir:

- `Tesouraria > Inadimplentes`

Validar:

- associados com mais de uma parcela vencida aparecem com todas as linhas no expand;
- parcelas antigas materializadas como `nao_descontado` aparecem mesmo quando há arquivos de retorno mais recentes;
- filtro por status `Não descontado` continua funcionando.

### 3. Verificação manual do detalhe do associado

Abrir:

- `Associados > selecionar associado > painel de ciclos`

Validar:

- a aba `Parcelas não descontadas` mostra apenas as competências ainda abertas;
- a aba `Quitadas fora do ciclo` aparece separadamente quando houver regularização histórica;
- clicar nos cards continua abrindo o `ParcelaDetalheDialog`.

## Rollback

Se precisar reverter:

```bash
git revert <commit>
docker compose up -d backend web
```
