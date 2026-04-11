# Deploy 2026-04-11

## Escopo aplicado

- Tesouraria:
  - corrige a separação entre `pendente` e `efetivado` quando o contrato já tem `auxilio_liberado_em` mas a esteira ainda não foi movida para `concluido`;
  - adiciona averbação direta para contratos `sem mensalidade`;
  - mantém `sem_pagamento_inicial` para contratos sem cobrança mensal, mesmo após averbação;
  - libera leitura de `contratos`, `pagamentos`, `confirmacoes` e `despesas` para `COORDENADOR`, mantendo bloqueio de ações mutáveis;
  - reduz custo da rota `tesouraria/pagamentos` no caso comum, paginando antes da projeção pesada.

- Dashboard / Análise:
  - adiciona a seção `Novos Contratos` como primeira seção do dashboard de análise;
  - mantém os cards da análise navegáveis e adiciona tooltip nas nomenclaturas mais operacionais.

- Coordenação / navegação:
  - renomeia `Aptos a Renovar` para `Validação de Renovação`;
  - expõe as rotas e subrotas de tesouraria para coordenação na navegação e no controle de acesso.

- Cadastros:
  - permite cadastro com `mensalidade = 0`;
  - adiciona a regra visual `Associado sem mensalidade` no formulário;
  - envia esses casos para fluxo de averbação direta na tesouraria.

- Dashboard de agentes:
  - corrige o ranking para usar a soma de `margem_disponivel` como volume de auxílio liberado.

## Arquivos centrais

- `backend/apps/tesouraria/views.py`
- `backend/apps/tesouraria/services.py`
- `backend/apps/tesouraria/serializers.py`
- `backend/apps/tesouraria/initial_payment.py`
- `backend/apps/esteira/analise_services.py`
- `backend/apps/relatorios/dashboard_service.py`
- `backend/apps/contratos/cycle_projection.py`
- `apps/web/src/app/(dashboard)/tesouraria/page.tsx`
- `apps/web/src/app/(dashboard)/analise/page.tsx`
- `apps/web/src/components/associados/associado-form.tsx`
- `apps/web/src/lib/navigation.ts`

## Validação executada

- `python -m compileall` nos arquivos Python alterados e nos testes focados.
- `pnpm exec prettier --check` nos arquivos TS/TSX alterados.
- `pnpm --filter @abase/web exec jest --runInBand --runTestsByPath src/lib/navigation.test.ts --watch=false --forceExit`
- `pnpm --filter @abase/web exec tsc --noEmit -p tsconfig.typecheck.json --pretty false`

- Smoke transacional no container `backend` validando:
  - averbação direta de contrato sem mensalidade;
  - permanência de `sem_pagamento_inicial` após averbação;
  - listagem de efetivados por `auxilio_liberado_em`;
  - acesso de leitura da coordenação em tesouraria e bloqueio de `POST`;
  - ranking de agentes usando `margem_disponivel`;
  - cadastro com mensalidade zero e presença em `Novos Contratos`.

## Limitação conhecida do ambiente local

- A suíte Django completa continua bloqueada por problema pré-existente no banco de teste:
  - criação de `test_abase_v2` já existente;
  - reaplicação de migration com `Duplicate column name 'associado_id'`.

Esses erros não foram introduzidos por este patch; por isso a validação backend foi complementada com smoke checks transacionais no container principal.
