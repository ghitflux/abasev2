# Patch: Tesouraria > Contratos para Renovação

Data: 2026-04-15

## Objetivo
Corrigir a rota `Tesouraria > Contratos para Renovação` em três pontos:
- substituir filtros livres por seleção operacional de ciclo e número do ciclo;
- permitir retorno para pendente de pagamento em linhas efetivadas/canceladas;
- permitir limpeza real de linha operacional incorreta.

## Validação do caso real
Foi verificado diretamente no banco Docker o CPF `03488545369`.

Estado encontrado:
- Associada: `ELISETE LEITE DA SILVA`
- Status do associado: `inadimplente`
- Contrato ativo: `CTR-20250917142548-G192X`
- Refinanciamentos encontrados:
  - `id=1496`, status `desativado`, `cycle_key=2026-02|2026-03|2026-04`
  - `id=34`, status `efetivado`, `cycle_key=2025-10|2025-11|2025-12`

Conclusão:
- a linha exibida na seção de canceladas vinha de um refinanciamento `DESATIVADO` ainda visível na esteira;
- a rota não tinha ação para devolver esse registro para pendente nem para limpar a linha operacional incorreta.

## Backend alterado

### 1. Filtro de ciclo por múltiplos meses
Arquivo:
- `backend/apps/refinanciamento/views.py`

Ajuste:
- `cycle_key` agora aceita múltiplos meses separados por `,` ou `|`;
- cada mês selecionado é aplicado como filtro obrigatório em `cycle_key__icontains`.

Exemplos aceitos:
- `2026-04`
- `2026-04,2026-06`
- `2026-04|2026-05|2026-06`

### 2. Retorno para pendente de pagamento
Arquivos:
- `backend/apps/refinanciamento/services.py`
- `backend/apps/refinanciamento/views.py`

Novo fluxo:
- endpoint: `POST /api/v1/tesouraria/refinanciamentos/{id}/retornar-pendente/`
- permitido para status:
  - `efetivado`
  - `bloqueado`
  - `revertido`
  - `desativado`

Efeitos da ação:
- status do refinanciamento volta para `aprovado_para_renovacao`;
- limpa `bloqueado_por`, `efetivado_por`, `motivo_bloqueio`;
- limpa `executado_em` e `data_ativacao_ciclo`;
- zera `data_pagamento` dos comprovantes de pagamento;
- se existir pagamento de tesouraria vinculado à renovação, ele volta para `pendente` e `paid_at = null`.

### 3. Limpeza de linha operacional incorreta
Arquivos:
- `backend/apps/refinanciamento/services.py`
- `backend/apps/refinanciamento/views.py`

Novo fluxo:
- endpoint: `POST /api/v1/tesouraria/refinanciamentos/{id}/limpar-linha/`
- ação faz `soft delete` do refinanciamento operacional;
- remove a linha da rota sem hard delete do banco;
- mantém rastreabilidade via auditoria.

## Frontend alterado
Arquivo:
- `apps/web/src/app/(dashboard)/tesouraria/refinanciamentos/page.tsx`

### 1. Filtro de ciclo
Removido:
- campo texto livre para `cycle_key`

Adicionado:
- seleção por competência com `CalendarCompetencia`;
- botão `Adicionar mês`;
- chips clicáveis para remover mês selecionado;
- envio do filtro consolidado para o backend em formato CSV.

### 2. Número do ciclo
Removido:
- campo texto livre

Adicionado:
- seletor nativo com opções `1` a `12`.

### 3. Ações nas linhas históricas
Adicionado em `Efetivadas` e `Canceladas`:
- `Voltar para pendente`
- `Limpar linha`

Dialogs incluídos:
- confirmação para retorno à fila;
- confirmação para limpeza de linha operacional.

## Testes executados

### Backend
Comando:
```bash
docker compose exec -T -e DJANGO_SETTINGS_MODULE=config.settings.testing backend \
  python manage.py test --noinput \
  apps.refinanciamento.tests.test_refinanciamento_pagamentos.RefinanciamentoPagamentosTestCase.test_tesouraria_lista_filtra_por_ciclo_e_numero_ciclos \
  apps.refinanciamento.tests.test_refinanciamento_pagamentos.RefinanciamentoPagamentosTestCase.test_tesouraria_lista_filtra_por_multiplos_meses_do_ciclo \
  apps.refinanciamento.tests.test_refinanciamento_pagamentos.RefinanciamentoPagamentosTestCase.test_tesouraria_pode_retornar_efetivado_para_pendente_pagamento \
  apps.refinanciamento.tests.test_refinanciamento_pagamentos.RefinanciamentoPagamentosTestCase.test_coordenacao_pode_limpar_linha_operacional_incorreta
```

Resultado:
- `4 tests` passando

Observação operacional:
- foi necessário limpar o banco de teste MySQL porque havia sobra de execução anterior:
```bash
docker compose exec -T mysql mysql -uabase -pabase -e "DROP DATABASE IF EXISTS test_test_abase_v2;"
```

### Frontend
Comando:
```bash
cd apps/web && npx jest --runTestsByPath "src/app/(dashboard)/tesouraria/refinanciamentos/page.test.tsx" --runInBand
```

Resultado:
- `6 tests` passando

## Arquivos alterados neste patch
- `backend/apps/refinanciamento/services.py`
- `backend/apps/refinanciamento/views.py`
- `backend/apps/refinanciamento/tests/test_refinanciamento_pagamentos.py`
- `apps/web/src/app/(dashboard)/tesouraria/refinanciamentos/page.tsx`
- `apps/web/src/app/(dashboard)/tesouraria/refinanciamentos/page.test.tsx`

## Aplicação no servidor
Como o projeto usa bind mount para código, o deploy operacional normalmente exige apenas reinício dos serviços afetados:
- `backend`
- `frontend`
- `celery` se houver consumo indireto de estado de refinanciamento

Comando sugerido:
```bash
docker compose restart backend frontend celery
```

## Smoke test pós-deploy
1. Abrir `Tesouraria > Contratos para Renovação`.
2. Abrir filtros avançados.
3. Selecionar um mês de ciclo, adicionar, aplicar e validar recorte.
4. Selecionar `Número do ciclo` e validar recorte.
5. Em uma linha `Efetivada`, usar `Voltar para pendente` e validar migração para a seção pendente.
6. Em uma linha incorreta de `Canceladas`, usar `Limpar linha` e validar remoção da esteira.
7. Validar o caso da Elisete após a ação escolhida pela operação.
