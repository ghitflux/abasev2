# Patch 2026-04-16: Materializacao Correta dos Ciclos dos Efetivados de Abril

## Objetivo

Corrigir a materializacao dos ciclos dos refinanciamentos `efetivado` em `04/2026` para que:

- o ciclo vigente tenha sempre `3` ou `4` parcelas, conforme o contrato;
- `04/2026` permaneça dentro do ciclo vigente quando ainda nao houver baixa material;
- o ciclo vigente fique `aberto`, e nao `pendencia`, quando a unica parcela faltante for a competencia corrente em `em_previsao`;
- o proximo ciclo continue sendo materializado normalmente, sem roubar `04/2026`;
- o repair da coorte de abril seja repetivel no servidor apos deploy.

## Problema encontrado

Na coorte de `23` refinanciamentos `efetivado` em `04/2026`, havia contratos em que:

- o ciclo vigente ficava com apenas `2` parcelas;
- `04/2026` saia do ciclo vigente;
- o proximo ciclo nascia cedo demais, incluindo `04/2026`;
- contratos com `admin_manual_layout_enabled = true` mantinham `status` e referencias antigas mesmo depois do rebuild;
- em casos com `ref1/ref2` apenas ate `03/2026`, a renovacao efetivada em abril empurrava o novo ciclo para o mes errado.

Caso de referencia validado:

- `JOSE AMERICO DE OLIVEIRA`
- CPF `19279841300`

Comportamento esperado:

- `ciclo 1` concluido;
- `ciclo 2` com `02/2026`, `03/2026` pagos e `04/2026` em `em_previsao`;
- `ciclo 3` materializado com `05/2026`, `06/2026`, `07/2026`.

## Causa raiz

Havia quatro defeitos combinados:

1. o status de ciclo renovado estava virando `pendencia` quando a ultima parcela do ciclo era apenas a competencia corrente em `em_previsao`;
2. no ramo manual, o rebuild nao atualizava ciclos ja existentes, apenas criava os faltantes;
3. o `first_reference` da renovacao efetiva podia abrir o proximo ciclo no proprio mes de abril quando o refinanciamento vinha com apenas `2/3` referencias pagas;
4. a projecao manual confiava demais no layout materializado quebrado e nao reidratava referencias pagas a partir do financeiro.

## O que foi alterado

### Backend

- [backend/apps/contratos/cycle_projection.py](/mnt/d/apps/abasev2/abasev2/backend/apps/contratos/cycle_projection.py)
  - ciclos renovados agora ficam `aberto` quando a unica pendencia e a competencia corrente em `em_previsao`;
  - `04/2026` deixa de sair do ciclo vigente nesses casos;
  - o `first_reference` de renovacao efetiva com `2/3` ou `3/4` parcelas pagas passa a abrir o proximo ciclo no mes seguinte ao mes corrente da renovacao;
  - a projecao manual passou a:
    - alinhar ciclos renovados ao `first_reference` correto;
    - completar a competencia faltante do ciclo vigente;
    - reidratar referencias pagas a partir do financeiro;
    - atualizar `data_inicio` e `data_fim` conforme as referencias reais do ciclo.

- [backend/apps/contratos/cycle_rebuild.py](/mnt/d/apps/abasev2/abasev2/backend/apps/contratos/cycle_rebuild.py)
  - no ramo `admin_manual_layout_enabled`, o rebuild agora reconcilia ciclos existentes com a projecao manual-aware;
  - ciclos e parcelas existentes passam a ter `status`, referencias e contagem corrigidos;
  - ciclos extras ou parcelas extras fora da projecao correta sao limpos.

### Testes

- [backend/apps/contratos/tests/test_cycle_projection.py](/mnt/d/apps/abasev2/abasev2/backend/apps/contratos/tests/test_cycle_projection.py)
  - caso cobrindo ciclo vigente com `04/2026` em `em_previsao` e ciclo futuro materializado;
  - caso cobrindo rebuild de contrato manual com status de ciclo atualizado apos renovacao efetiva;
  - caso cobrindo renovacao efetiva com apenas referencias pagas (`ref1/ref2`) em que abril deve permanecer no ciclo vigente e o ciclo seguinte deve iniciar em maio.

## Comando de reparo

- [backend/apps/refinanciamento/management/commands/repair_april_effectivated_cycle_materialization.py](/mnt/d/apps/abasev2/abasev2/backend/apps/refinanciamento/management/commands/repair_april_effectivated_cycle_materialization.py)

Esse comando:

- audita a coorte `efetivado` da competencia informada;
- compara ciclo vigente e proximo ciclo com a projecao corrigida;
- reconstroi os contratos inconsistentes;
- grava relatorio JSON em `media/relatorios`.

Uso manual:

```bash
docker compose exec -T backend python manage.py repair_april_effectivated_cycle_materialization --competencia 2026-04
docker compose exec -T backend python manage.py repair_april_effectivated_cycle_materialization --competencia 2026-04 --apply
```

## Script de servidor

- [scripts/post_deploy_april_effectivated_cycle_materialization_repair.sh](/mnt/d/apps/abasev2/abasev2/scripts/post_deploy_april_effectivated_cycle_materialization_repair.sh)

Uso:

```bash
bash scripts/post_deploy_april_effectivated_cycle_materialization_repair.sh 2026-04
```

O script:

- roda auditoria antes;
- aplica a correcao;
- roda auditoria depois;
- reinicia o backend.

## Validacao local

### Resultado da coorte de abril

Ao final da correcao local em `16/04/2026`:

- `23` refinanciamentos auditados em `04/2026`
- `0` refinanciamentos com problema apos o repair

### Validacao de negocio da coorte

Checagem de negocio aplicada aos `23` casos:

- `0` ciclos vigentes com tamanho menor que o tamanho real do contrato;
- `0` contratos com `04/2026` fora do ciclo vigente;
- `0` proximos ciclos com inicio em `04/2026` quando o ciclo vigente ainda dependia dessa competencia;
- `0` ciclos vigentes em `pendencia` apenas por renovacao antecipada.

### Caso de referencia

`JOSE AMERICO DE OLIVEIRA / 19279841300` ficou assim:

- `ciclo 1`: `ciclo_renovado`
- `ciclo 2`: `aberto` com `02/2026` e `03/2026` `descontado`, `04/2026` `em_previsao`
- `ciclo 3`: `aberto` com `05/2026`, `06/2026`, `07/2026` `em_previsao`

## Passo a passo pos-deploy

### 1. Subir a atualizacao

```bash
cd /app
git pull
docker compose build backend web
docker compose up -d backend web
```

### 2. Rodar o repair da coorte de abril

```bash
bash scripts/post_deploy_april_effectivated_cycle_materialization_repair.sh 2026-04
```

### 3. Verificacao pos-deploy

Conferir:

- `Tesouraria > Contratos para Renovacao > Efetivadas`
- detalhes do associado de um caso de abril
- especialmente `JOSE AMERICO DE OLIVEIRA / 19279841300`

Esperado:

- ciclo vigente com `3/3` ou `4/4` referencias do grupo correto;
- `04/2026` no ciclo vigente, e nao fora dele;
- proximo ciclo materializado com inicio somente no mes seguinte;
- sem `pendencia` artificial quando abril ainda estiver apenas em `em_previsao`.
