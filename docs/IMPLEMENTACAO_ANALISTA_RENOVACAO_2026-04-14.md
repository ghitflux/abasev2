# Implementação Analista e Contratos para Renovação

Data: 2026-04-14

## Escopo concluído

### Rota: Analista

- [x] Ajustar esteira de status no módulo `dashboard.analise`
- [x] Permitir reprovação pelo analista com exclusão correta do cadastro do associado
- [x] Exibir valor da doação nos detalhes do associado para analista e demais perfis

### Rota: Contratos para Renovação

- [x] Parar de sobrescrever renovações anteriores
- [x] Adicionar filtro por ciclo
- [x] Otimizar a rota para expandir a linha do associado
- [x] Permitir expandir cada renovação e cada parcela

## O que foi alterado

### Esteira do analista

- A ação `reprovar` foi adicionada à etapa `analise:em_andamento`.
- A reprovação reutiliza a mesma exclusão lógica em cascata já validada na esteira:
  - associado
  - esteira
  - documentos
  - issues de documento
  - reuploads
  - árvore contratual operacional
- O dashboard `dashboard.analise` passou a exibir status com leitura mais consistente:
  - etapa operacional
  - situação atual
  - contexto documental

### Valor da doação

- O valor da doação passou a aparecer no diálogo de detalhes do associado.
- O valor também foi exposto no resumo do contrato dentro do histórico de contratos e ciclos.

### Histórico de renovação

- A seleção da renovação operacional ativa foi endurecida para não reutilizar registros já efetivados/concluídos.
- O rebuild de ciclos e a estratégia de elegibilidade agora distinguem:
  - renovação ativa em aberto
  - renovação histórica já efetivada
- Com isso, um novo ciclo apto gera uma nova renovação sem sobrescrever a anterior.

### Auditoria na rota `analise/aptos`

- Foi adicionado filtro por ciclo via `cycle_key`.
- A tabela agora permite expandir a linha do associado.
- A expansão mostra o histórico auditável do associado usando contratos, ciclos e parcelas.
- Os ciclos passaram a ser exibidos em acordeão, facilitando navegação por:
  - ciclo
  - parcelas do ciclo
  - anexos do ciclo

## Arquivos principais

- `backend/apps/esteira/services.py`
- `backend/apps/esteira/views.py`
- `backend/apps/esteira/tests/test_analise.py`
- `backend/apps/contratos/cycle_rebuild.py`
- `backend/apps/refinanciamento/payment_rules.py`
- `backend/apps/refinanciamento/services.py`
- `backend/apps/refinanciamento/tests/test_refinanciamento_pagamentos.py`
- `apps/web/src/app/(dashboard)/analise/page.tsx`
- `apps/web/src/app/(dashboard)/analise/aptos/page.tsx`
- `apps/web/src/components/associados/associado-contracts-overview.tsx`
- `apps/web/src/components/associados/associado-details-dialog.tsx`
- `apps/web/src/components/shared/data-table.tsx`

## Validação executada

- `python -m py_compile` nos arquivos backend alterados
- `git diff --check`
- `npx prettier --check` nos arquivos frontend alterados
- testes backend direcionados no container `abase-v2-backend-1`:
  - `test_reprovar_item_em_analise_remove_cadastro_completo`
  - `test_novo_ciclo_cria_nova_renovacao_sem_sobrescrever_historico_anterior`
  - `test_fluxo_devolucao_de_termo_reaproveita_mesmo_refinanciamento`
  - `test_analise_resumo_refinanciamentos_retorna_cards_operacionais`

## Observação de ambiente

- O `pnpm --filter @abase/web type-check` continua falhando por erro preexistente em `apps/web/src/components/shared/report-export-dialog.tsx`, fora do escopo desta entrega.
