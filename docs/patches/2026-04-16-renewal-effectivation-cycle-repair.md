# Patch 2026-04-16: Efetivacao de Renovacao, Retorno para Ativo e Geracao do Novo Ciclo

## Objetivo

Corrigir o fluxo de renovacao quando a tesouraria efetiva:

- o associado deve sair do estado operacional de renovacao e voltar para `ativo`
- o contrato deve materializar o novo ciclo
- o novo ciclo deve nascer com parcelas futuras (`em_previsao`)
- o `refinanciamento.efetivado` deve ficar vinculado ao `ciclo_destino`

Complemento de abril/2026:

- a materializacao fina do ciclo vigente e do ciclo seguinte da coorte `04/2026`
  foi detalhada em [2026-04-16-april-effectivated-cycle-materialization.md](/mnt/d/apps/abasev2/abasev2/docs/patches/2026-04-16-april-effectivated-cycle-materialization.md)

## Problema encontrado

Havia varios casos de renovacao `efetivado` em que:

- o associado nao voltava para `ativo`
- `ciclo_destino` ficava nulo
- o novo ciclo nao era gerado

Na auditoria local em `16/04/2026`, antes da correcao:

- `396` refinanciamentos `efetivado`
- `68` com associado fora de `ativo`
- `155` sem `ciclo_destino`

No recorte da competencia `2026-04`, antes da correcao:

- `23` refinanciamentos `efetivado`
- `14` sem `ciclo_destino`

## Causa raiz

O principal defeito estava na trilha de contratos com `admin_manual_layout_enabled = true`.

Nessa trilha:

- a projecao manual nao considerava corretamente `effective renewals` para criar o ciclo seguinte
- o `rebuild_contract_cycle_state()` nao materializava ciclos futuros faltantes no ramo manual
- o servico de `efetivar()` nao sincronizava o `Associado.status` ao final do processo

Resultado:

- a renovacao ficava marcada como `efetivado`
- mas o contrato continuava parado no ciclo anterior
- e o associado podia continuar em status operacional incorreto

## O que foi alterado

### Backend

- [backend/apps/contratos/cycle_projection.py](/mnt/d/apps/abasev2/abasev2/backend/apps/contratos/cycle_projection.py)
  - a projecao manual agora considera `effective renewals`
  - ciclos existentes passam a refletir renovacao posterior:
    - ciclo anterior deixa de ficar `apto_a_renovar` quando ja existe renovacao efetivada
    - novo ciclo sintetico e projetado com parcelas `em_previsao`
  - a projecao do contrato manual agora consegue expor o ciclo futuro para o rebuild

- [backend/apps/contratos/cycle_rebuild.py](/mnt/d/apps/abasev2/abasev2/backend/apps/contratos/cycle_rebuild.py)
  - no ramo de `admin_manual_layout_enabled`, o rebuild passou a:
    - criar ciclos futuros faltantes
    - reutilizar ciclos soft-deletados com o mesmo numero, quando existirem
    - criar/reaproveitar parcelas do novo ciclo
    - sincronizar o `ciclo_destino` do refinanciamento efetivado

- [backend/apps/refinanciamento/services.py](/mnt/d/apps/abasev2/abasev2/backend/apps/refinanciamento/services.py)
  - `efetivar()` agora:
    - roda o rebuild
    - tenta vincular explicitamente o `ciclo_destino` ao `ciclo_origem.numero + 1`
    - sincroniza `Associado.status` ao final

### Teste

- [backend/apps/refinanciamento/tests/test_refinanciamento_pagamentos.py](/mnt/d/apps/abasev2/abasev2/backend/apps/refinanciamento/tests/test_refinanciamento_pagamentos.py)
  - adicionado caso de contrato manual em que:
    - a renovacao e efetivada
    - o associado volta para `ativo`
    - o `ciclo_destino` e criado
    - o novo ciclo vem com `3` parcelas `em_previsao`

### Comando de reparo

- [backend/apps/refinanciamento/management/commands/repair_effectivated_renewal_cycles.py](/mnt/d/apps/abasev2/abasev2/backend/apps/refinanciamento/management/commands/repair_effectivated_renewal_cycles.py)
  - novo comando de auditoria/correcao para refinanciamentos efetivados
  - uso recomendado:
    - com `--competencia YYYY-MM` para o recorte operacional atual
    - sem competencia para auditoria historica conservadora

### Script de servidor

- [scripts/post_deploy_effectivated_renewal_cycle_repair.sh](/mnt/d/apps/abasev2/abasev2/scripts/post_deploy_effectivated_renewal_cycle_repair.sh)
  - roda auditoria antes
  - aplica a correcao da competencia
  - roda auditoria depois
  - roda auditoria historica conservadora
  - reinicia o backend

## Validacao local

### Caso real validado

Contrato ligado ao refinanciamento `#1690`:

- antes:
  - `ciclo_destino = null`
  - apenas `ciclo 1`
- depois:
  - `ciclo_destino` preenchido
  - `ciclo 2` materializado
  - projecao passou a mostrar:
    - `ciclo 2 = aberto`
    - `ciclo 1 = pendencia` / renovado na trilha correta

### Resultado apos correcao da competencia atual

Competencia `2026-04`:

- `23` refinanciamentos `efetivado`
- `0` associados fora de `ativo`
- `0` sem `ciclo_destino`
- `0` ciclos destino incompletos no recorte atual

### Auditoria historica apos ajuste

O comando sem `--competencia` ficou sem inconsistencias no criterio conservador atual:

- `Refinanciamentos efetivados auditados: 396`
- `Refinanciamentos efetivados com problema: 0`

## Passo a passo no servidor

### 1. Deploy

```bash
cd /app
git pull
docker compose build backend web
docker compose up -d backend web
```

### 2. Aplicar reparo da competencia operacional

```bash
bash scripts/post_deploy_effectivated_renewal_cycle_repair.sh 2026-04
```

### 3. Validacao manual

Conferir:

- `Tesouraria > Contratos para Renovacao > Efetivadas`
- um contrato efetivado recentemente
- detalhes do associado / meus contratos / parcela detalhe

Esperado:

- associado em `ativo`
- `status_renovacao = efetivado` no fluxo correto
- novo ciclo materializado
- parcelas futuras presentes no novo ciclo

## Observacao operacional

O comando historico sem `--competencia` e propositalmente conservador.

Ele nao trata como erro qualquer caso antigo em que o associado ja tenha voltado a ficar
`apto_a_renovar` legitimamente depois de completar o ciclo seguinte.

Para o pos-deploy, o uso principal deve ser sempre com a competencia operacional atual.
