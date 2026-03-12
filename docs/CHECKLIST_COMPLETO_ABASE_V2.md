# Checklist Completo ABASE v2

Atualizado em 2026-03-11.

## Resumo Geral

- [x] Semana 1 - Fundacao
- [ ] Semana 2 - CRUD + Esteira
- [x] Semana 3 - Tesouraria + Refinanciamento
- [x] Semana 4 - Arquivo Retorno + Polish

Status atual:
- Semana 1 esta concluida.
- Semana 2 esta com a implementacao principal entregue em backend e frontend, mas ainda ha pequenas pendencias de UX/validacao para considerar 100%.
- Semana 3 foi implementada neste repositorio, incluindo backend, frontend, testes de integracao e codegen atualizado.
- Semana 4 foi concluida neste repositorio, com parser ETIPI real, reconciliacao, renovacao de ciclos, frontend com Kubb, testes, hardening basico e documentacao de QA/setup local.

## Semana 1 - Fundacao

### Bloco 1 - Monorepo, frontend e Docker

- [x] `pnpm-workspace.yaml` configurado com `apps/*` e `packages/*`
- [x] `package.json` raiz com `packageManager: pnpm@9.15.0`
- [x] `.npmrc` com `link-workspace-packages=true`
- [x] Pacotes `@abase/tsconfig`, `@abase/eslint-config` e `@abase/shared-types` criados
- [x] `apps/web` configurado como `@abase/web`
- [x] Kubb configurado no frontend
- [x] Todos os componentes base do `shadcn/ui` presentes em `apps/web/src/components/ui/`
- [x] `docker-compose.yml` com 5 servicos (`mysql`, `redis`, `backend`, `celery`, `frontend`)
- [x] MySQL 8 e Redis 7 com healthchecks e volumes nomeados

### Bloco 2 - Backend, models e migrations

- [x] `BaseModel`, managers de soft delete e utilitarios core criados
- [x] App `accounts` com `User`, `Role`, `UserRole` e permissoes por role
- [x] Apps `associados`, `contratos`, `esteira`, `importacao`, `refinanciamento`, `tesouraria` e `relatorios` modelados
- [x] `ArquivoRetorno`, `ArquivoRetornoItem` e `ImportacaoLog` implementados
- [x] Migrations iniciais geradas para todos os apps da Semana 1
- [x] Fixture `roles.json` criada
- [x] Seed idempotente para roles e admin de desenvolvimento criado (`seed_dev_data`)

### Bloco 3 - Auth e componentes customizados

- [x] Endpoints JWT `login`, `refresh`, `logout` e `me`
- [x] `proxy.ts`, `auth-store.ts`, `use-auth.ts` e `use-permissions.ts`
- [x] Pagina de login integrada ao backend
- [x] 14 componentes customizados criados em `apps/web/src/components/custom/`
- [x] `src/lib/masks.ts` com mascaras e validacoes base

### Bloco 4 - Layout base

- [x] Layout principal em `apps/web/src/app/(dashboard)/layout.tsx`
- [x] Sidebar responsiva com navegacao condicional por role
- [x] Header principal com busca, filtros e sessao
- [x] Componentes shared (`StatsCard`, `DataTable`, `FilterAdvanced`, `ExportButton`, `EmptyState`)

## Semana 2 - CRUD + Esteira

### Bloco 5 - CRUD Associados Backend

- [x] `AssociadoListSerializer`, `AssociadoDetailSerializer`, `AssociadoCreateSerializer`, `AssociadoUpdateSerializer` e `AssociadoMetricasSerializer`
- [x] `AssociadoFilter` implementado
- [x] `AssociadoService` com `calcular_metricas()` e `criar_associado_completo()`
- [x] `AssociadoFactory` para PF e PJ
- [x] `ValidationStrategy` para cadastro e edicao
- [x] `AssociadoViewSet` com `metricas`, `ciclos` e `documentos`
- [x] Router DRF atualizado com `associados`, `esteira` e `contratos`
- [x] Migrations da Semana 2 geradas e aplicadas para `associados`, `contratos` e `esteira`
- [x] POST de criacao atomico com `transaction.atomic()`

### Bloco 6 - CRUD Associados Frontend

- [x] Tela `src/app/(dashboard)/associados/page.tsx` com metricas, busca, filtros e tabela
- [x] Row expansivel com ciclos e parcelas
- [x] Formulario multi-step de cadastro em `src/components/associados/associado-form.tsx`
- [x] Pagina `src/app/(dashboard)/associados/novo/page.tsx`
- [x] Pagina de detalhe `src/app/(dashboard)/associados/[id]/page.tsx`
- [x] Pagina de edicao `src/app/(dashboard)/associados/[id]/editar/page.tsx`
- [x] Proxy autenticado para chamadas ao backend em `src/app/api/backend/[...path]/route.ts`

### Bloco 7 - Esteira de Analise

- [x] `EsteiraService` como state machine
- [x] `ApprovalStrategy` para Analista e Coordenador
- [x] `EsteiraViewSet` com `assumir`, `aprovar`, `pendenciar`, `validar-documento`, `solicitar-correcao` e `transicoes`
- [x] Dashboard do analista em `src/app/(dashboard)/analise/page.tsx`
- [x] Esteira de pendencias do agente em `src/app/(dashboard)/agentes/esteira-pendencias/page.tsx`
- [x] Registro de `Transicao` para audit trail
- [x] Dialog de confirmacao para `assumir`
- [ ] Dialog de confirmacao especifico para `aprovar`
- [ ] Validacao ponta a ponta do fluxo `assumir -> aprovar -> tesouraria`

### Bloco 8 - Contratos do Agente

- [x] `ContratoViewSet` com `resumo`
- [x] Tela `src/app/(dashboard)/agentes/meus-contratos/page.tsx`
- [x] Resumo com cards, filtros, tabela e badges de refinanciamento

### Integracao e geracao de API

- [x] `schema.yaml` regenerado a partir do backend
- [x] Kubb executado com geracao de `apps/web/src/gen`
- [x] `apps/web/kubb.config.js` criado para destravar o codegen no ambiente atual
- [x] Formatacao automatica dos arquivos gerados pelo Kubb

Motivo:
O codegen roda, gera os arquivos corretamente e a formatacao automatica foi explicitada com `prettier` no frontend para validacao no container.

### Validacoes executadas na Semana 2

- [x] `docker compose exec -T backend python manage.py makemigrations associados contratos esteira`
- [x] `docker compose exec -T backend python manage.py migrate`
- [x] `docker compose exec -T backend python manage.py check`
- [x] `docker compose exec -T backend python manage.py spectacular --file /app/schema.yaml --validate`
- [x] `docker compose exec -T frontend pnpm --filter @abase/web generate:api`
- [x] `docker compose exec -T frontend pnpm --filter @abase/web type-check`
- [x] `docker compose exec -T frontend pnpm --filter @abase/web build`
- [x] Smoke test autenticado de `POST /api/v1/associados/`
- [x] Smoke test autenticado de `GET /api/v1/associados/metricas/`
- [x] Smoke test autenticado de `GET /api/v1/esteira/`
- [x] Smoke test autenticado de `GET /api/v1/contratos/resumo/`

## Semana 3 - Tesouraria + Refinanciamento

- [x] Dashboard de tesouraria
- [x] Efetivacao com comprovante PIX
- [x] Tela de confirmacoes (ligacao e averbacao)
- [x] Fluxo de refinanciamento
- [x] Telas de coordenacao
- [x] Refinanciamentos do tesoureiro

### Entregas implementadas na Semana 3

- [x] `backend/apps/tesouraria/services.py` com efetivacao, congelamento, confirmacoes e dados bancarios
- [x] `backend/apps/tesouraria/views.py` com rotas `/api/v1/tesouraria/contratos/` e `/api/v1/tesouraria/confirmacoes/`
- [x] `backend/apps/refinanciamento/services.py` com elegibilidade, solicitacao, aprovacao, bloqueio, reversao e efetivacao
- [x] `backend/apps/refinanciamento/views.py` com rotas de agente, coordenacao e tesouraria
- [x] Migrations novas para `refinanciamento` e `tesouraria`
- [x] Testes de integracao da Semana 3 em `backend/apps/tesouraria/tests/test_fluxo_completo.py`
- [x] Tela `apps/web/src/app/(dashboard)/tesouraria/page.tsx`
- [x] Tela `apps/web/src/app/(dashboard)/tesouraria/confirmacoes/page.tsx`
- [x] Tela `apps/web/src/app/(dashboard)/agentes/refinanciados/page.tsx`
- [x] Tela `apps/web/src/app/(dashboard)/coordenacao/refinanciados/page.tsx`
- [x] Tela `apps/web/src/app/(dashboard)/coordenacao/refinanciamento/page.tsx`
- [x] Tela `apps/web/src/app/(dashboard)/tesouraria/refinanciamentos/page.tsx`
- [x] Acao real de solicitar refinanciamento em `apps/web/src/app/(dashboard)/agentes/meus-contratos/page.tsx`

### Validacoes executadas na Semana 3

- [x] `docker compose exec -T backend python manage.py makemigrations refinanciamento tesouraria`
- [x] `docker compose exec -T backend python manage.py migrate`
- [x] `docker compose exec -T backend python manage.py check`
- [x] `docker compose exec -T -e DJANGO_SETTINGS_MODULE=config.settings.testing backend python manage.py test apps.tesouraria.tests.test_fluxo_completo -v 2`
- [x] `docker compose exec -T backend python manage.py spectacular --file /app/schema.yaml --validate`
- [x] `docker compose exec -T frontend pnpm --filter @abase/web generate:api`
- [x] `pnpm --filter @abase/web exec tsc --noEmit`
- [x] `docker compose exec -T frontend pnpm --filter @abase/web build`

## Semana 4 - Arquivo Retorno + Polish

- [x] Backend do Arquivo Retorno (`parsers`, `services`, `tasks`, `reconciliacao`)
- [x] Frontend de upload e historico do Arquivo Retorno
- [x] Renovacao automatica de ciclos
- [x] Integracao OpenAPI + consumo real no frontend
- [x] Testes automatizados e hardening de seguranca
- [x] Documentacao final e QA manual (sem deploy)

### Validacoes executadas na Semana 4

- [x] `docker compose exec -T -e DJANGO_SETTINGS_MODULE=config.settings.testing backend python manage.py test apps.importacao apps.contratos -v 2`
- [x] `docker compose exec -T frontend pnpm --filter @abase/web test`
- [x] `docker compose exec -T frontend pnpm --filter @abase/web type-check`
- [x] `docker compose exec -T frontend pnpm --filter @abase/web build`
- [x] `docker compose exec -T backend python manage.py spectacular --file /app/schema.yaml --validate`
- [x] `docker compose exec -T backend python manage.py check`
- [x] `docs/QA_SEMANA_4.md` entregue
- [x] `docs/SETUP_LOCAL.md` entregue

## Arquivos-chave do progresso atual

- [x] `backend/apps/associados/serializers.py`
- [x] `backend/apps/associados/services.py`
- [x] `backend/apps/associados/views.py`
- [x] `backend/apps/esteira/services.py`
- [x] `backend/apps/esteira/views.py`
- [x] `backend/apps/contratos/views.py`
- [x] `apps/web/src/app/(dashboard)/associados/page.tsx`
- [x] `apps/web/src/app/(dashboard)/analise/page.tsx`
- [x] `apps/web/src/app/(dashboard)/agentes/esteira-pendencias/page.tsx`
- [x] `apps/web/src/app/(dashboard)/agentes/meus-contratos/page.tsx`
- [x] `apps/web/src/components/associados/associado-form.tsx`
- [x] `apps/web/src/gen/`
