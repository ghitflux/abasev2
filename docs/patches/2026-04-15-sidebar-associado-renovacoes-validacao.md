# Patch 2026-04-15: Sidebar + Associado + Renovações

## Escopo
- aumentar a largura da sidebar para evitar abreviação de rotas;
- remover a exclusão de associado do detalhe e bloquear `DELETE` no backend;
- adicionar filtros por ciclo e número do ciclo em `Tesouraria > Contratos para Renovação`;
- permitir limpar linhas incorretas da fila de renovação;
- garantir por teste que o status do associado permanece no estado de cadastro até a efetivação explícita da tesouraria.

## Validação das mudanças locais pré-existentes

### Mudanças já existentes no workspace antes desta sessão
- em [page.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/app/(dashboard)/tesouraria/refinanciamentos/page.tsx):
  - efetivação de renovação passou a depender de ação explícita;
  - ação `Remover da fila` foi adicionada para renovação;
  - tela passou a usar `Dialog` para remoção, mas sem os imports necessários.
- em [views.py](/mnt/d/apps/abasev2/abasev2/backend/apps/refinanciamento/views.py):
  - `efetivar` passou a aceitar JSON/FormData sem exigir upload direto;
  - action `excluir` foi adicionada à tesouraria de renovações.
- em [page.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/app/(dashboard)/associados/[id]/page.tsx) e [views.py](/mnt/d/apps/abasev2/abasev2/backend/apps/associados/views.py):
  - a exclusão do associado foi remodelada para “remoção operacional preservando histórico”.

### Resultado da validação dessas mudanças
- a parte de renovações estava conceitualmente correta, mas incompleta:
  - faltavam imports de `Dialog` no frontend;
  - faltavam filtros por ciclo e número do ciclo;
  - havia testes com expectativa incorreta sobre persistência de comprovante parcial em transação inválida.
- a parte de exclusão de associado estava incompatível com a regra de negócio pedida:
  - associado não pode ser excluído;
  - essa implementação foi descartada e substituída por bloqueio total de `DELETE`.

## Correções aplicadas nesta sessão

### 1. Sidebar
- aumentada de `16rem` para `20rem` em [sidebar.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/components/ui/sidebar.tsx).
- objetivo: reduzir truncamento de títulos como `Contratos para Renovação`.

### 2. Associado não pode ser excluído

#### Backend
- `DELETE /associados/{id}/` agora retorna `405` com mensagem explícita:
  - `Associado não pode ser excluído. Utilize a inativação.`
- arquivo: [views.py](/mnt/d/apps/abasev2/abasev2/backend/apps/associados/views.py)

#### Frontend
- removidos do detalhe do associado:
  - botão de exclusão;
  - diálogo de confirmação de exclusão;
  - mutation de `DELETE`.
- mantida apenas a ação de inativação.
- arquivo: [page.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/app/(dashboard)/associados/[id]/page.tsx)

#### Testes
- testes antigos de exclusão foram substituídos por testes que garantem o bloqueio da operação.
- arquivo: [test_permissions.py](/mnt/d/apps/abasev2/abasev2/backend/apps/associados/tests/test_permissions.py)
- a suíte da página do associado foi estabilizada para React 19/Suspense com `act(async ...)`.
- arquivo: [page.test.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/app/(dashboard)/associados/[id]/page.test.tsx)

### 3. Renovações: filtro por ciclo e número do ciclo

#### Backend
- adicionado suporte ao query param `numero_ciclos` em [views.py](/mnt/d/apps/abasev2/abasev2/backend/apps/refinanciamento/views.py)
- regra:
  - `cycle_key` continua filtrando o ciclo por texto/competência;
  - `numero_ciclos` filtra por `ciclo_origem__numero`;
  - valor inválido retorna erro estruturado de validação.

#### Frontend
- adicionados no drawer de filtros avançados:
  - `Ciclo`
  - `Número do ciclo`
- os filtros agora alimentam:
  - listagem pendente;
  - listagem efetivada;
  - listagem cancelada;
  - resumo;
  - exportação.
- arquivo: [page.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/app/(dashboard)/tesouraria/refinanciamentos/page.tsx)

#### Testes
- incluído teste backend para `cycle_key + numero_ciclos`.
- incluído teste frontend para garantir que a tela envia os dois filtros.
- arquivos:
  - [test_refinanciamento_pagamentos.py](/mnt/d/apps/abasev2/abasev2/backend/apps/refinanciamento/tests/test_refinanciamento_pagamentos.py)
  - [page.test.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/app/(dashboard)/tesouraria/refinanciamentos/page.test.tsx)

### 4. Limpeza de linha incorreta na fila de renovação

#### Backend
- mantida e validada a action `POST /tesouraria/refinanciamentos/{id}/excluir/`
- comportamento validado:
  - a linha sai da fila pendente;
  - o histórico é preservado via bloqueio operacional.

#### Frontend
- mantido o botão `Remover da fila`;
- corrigidos imports de `Dialog`;
- incluído teste cobrindo abertura do diálogo e chamada da action de exclusão.

### 5. Status do associado durante cadastro
- regra validada por teste:
  - o associado mantém o status inicial durante o processo de cadastro;
  - anexar comprovante isolado não ativa o associado;
  - efetivação inválida sem comprovante completo não ativa o associado;
  - o associado só vira `ativo` após a efetivação explícita da tesouraria.
- arquivo: [test_fluxo_completo.py](/mnt/d/apps/abasev2/abasev2/backend/apps/tesouraria/tests/test_fluxo_completo.py)

## Ajustes de teste importantes
- testes de `efetivar` sem comprovante completo foram corrigidos para refletir o comportamento transacional real:
  - a operação inválida faz rollback;
  - não deve sobrar comprovante parcial salvo.

## Arquivos alterados
- [sidebar.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/components/ui/sidebar.tsx)
- [page.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/app/(dashboard)/associados/[id]/page.tsx)
- [page.test.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/app/(dashboard)/associados/[id]/page.test.tsx)
- [page.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/app/(dashboard)/tesouraria/refinanciamentos/page.tsx)
- [page.test.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/app/(dashboard)/tesouraria/refinanciamentos/page.test.tsx)
- [views.py](/mnt/d/apps/abasev2/abasev2/backend/apps/associados/views.py)
- [test_permissions.py](/mnt/d/apps/abasev2/abasev2/backend/apps/associados/tests/test_permissions.py)
- [views.py](/mnt/d/apps/abasev2/abasev2/backend/apps/refinanciamento/views.py)
- [test_refinanciamento_pagamentos.py](/mnt/d/apps/abasev2/abasev2/backend/apps/refinanciamento/tests/test_refinanciamento_pagamentos.py)
- [test_fluxo_completo.py](/mnt/d/apps/abasev2/abasev2/backend/apps/tesouraria/tests/test_fluxo_completo.py)

## Testes executados

### Backend
Executado no container `backend` com `DJANGO_SETTINGS_MODULE=config.settings.testing`, porque a execução local tentou conectar no MySQL fora do Docker com credencial incorreta.

Comando validado:

```bash
docker compose exec -T -e DJANGO_SETTINGS_MODULE=config.settings.testing backend \
  python manage.py test --noinput \
  apps.associados.tests.test_permissions.AssociadoPermissionsTestCase.test_admin_nao_pode_excluir_associado \
  apps.associados.tests.test_permissions.AssociadoPermissionsTestCase.test_coordenador_nao_pode_excluir_associado \
  apps.refinanciamento.tests.test_refinanciamento_pagamentos.RefinanciamentoPagamentosTestCase.test_tesouraria_efetiva_refinanciamento_sem_comprovante_do_agente \
  apps.refinanciamento.tests.test_refinanciamento_pagamentos.RefinanciamentoPagamentosTestCase.test_substituir_comprovante_nao_efetiva_refinanciamento \
  apps.refinanciamento.tests.test_refinanciamento_pagamentos.RefinanciamentoPagamentosTestCase.test_tesouraria_efetiva_refinanciamento_com_comprovantes_ja_anexados \
  apps.refinanciamento.tests.test_refinanciamento_pagamentos.RefinanciamentoPagamentosTestCase.test_coordenador_pode_remover_renovacao_da_fila_tesouraria \
  apps.refinanciamento.tests.test_refinanciamento_pagamentos.RefinanciamentoPagamentosTestCase.test_tesouraria_lista_filtra_por_ciclo_e_numero_ciclos \
  apps.tesouraria.tests.test_fluxo_completo.TestFluxoCompleto.test_efetivacao_sem_comprovante_do_agente_falha \
  apps.tesouraria.tests.test_fluxo_completo.TestFluxoCompleto.test_substituir_comprovante_nao_efetiva_sem_acao_explicita \
  apps.tesouraria.tests.test_fluxo_completo.TestFluxoCompleto.test_efetivacao_com_comprovantes_ja_anexados_exige_acao_explicita
```

Resultado:
- `10 tests` passando.

### Frontend
Comandos executados:

```bash
pnpm --dir apps/web exec jest --runInBand --forceExit --testTimeout=20000 \
  --runTestsByPath 'src/app/(dashboard)/associados/[id]/page.test.tsx'

pnpm --dir apps/web exec jest --runInBand --forceExit --testTimeout=20000 \
  --runTestsByPath 'src/app/(dashboard)/tesouraria/refinanciamentos/page.test.tsx'

pnpm --dir apps/web exec jest --runInBand --forceExit --testTimeout=20000 \
  --runTestsByPath 'src/components/layout/app-sidebar.test.tsx'
```

Resultados:
- `page.test.tsx` do associado: `2 tests` passando.
- `page.test.tsx` de renovações: `5 tests` passando.
- `app-sidebar.test.tsx`: `2 tests` passando.

## Conclusão
- as mudanças locais pré-existentes de renovação foram aproveitadas e validadas;
- as mudanças locais pré-existentes de exclusão de associado foram rejeitadas e substituídas pela regra correta;
- o sistema agora respeita:
  - associado somente inativável;
  - ativação apenas na efetivação da tesouraria;
  - filtro de renovações por ciclo e número do ciclo;
  - limpeza de linha incorreta na fila de renovação;
  - sidebar mais larga para reduzir abreviação de rotas.
