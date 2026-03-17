# Checklist Semana 1

Atualizado em 2026-03-11.

## Bloco 1 - Monorepo, frontend e Docker

- [x] `pnpm-workspace.yaml` configurado com `apps/*` e `packages/*`
- [x] `package.json` raiz com `packageManager: pnpm@9.15.0`
- [x] `.npmrc` com `link-workspace-packages=true`
- [x] Pacotes `@abase/tsconfig`, `@abase/eslint-config` e `@abase/shared-types` criados
- [x] `apps/web` configurado como `@abase/web`
- [x] `kubb.config.ts` configurado no frontend
- [x] Todos os componentes base do `shadcn/ui` presentes em `apps/web/src/components/ui/`
- [x] `docker-compose.yml` com 5 servicos (`mysql`, `redis`, `backend`, `celery`, `frontend`)
- [x] MySQL 8 e Redis 7 com healthchecks e volumes nomeados

## Bloco 2 - Backend, models e migrations

- [x] `BaseModel`, managers de soft delete e utilitarios core criados
- [x] App `accounts` com `User`, `Role`, `UserRole` e permissoes por role
- [x] Apps `associados`, `contratos`, `esteira`, `importacao`, `refinanciamento`, `tesouraria` e `relatorios` modelados
- [x] `ArquivoRetorno`, `ArquivoRetornoItem` e `ImportacaoLog` implementados
- [x] Migrations iniciais geradas para todos os apps da semana 1
- [x] Fixture `roles.json` criada
- [x] Seed idempotente para roles e admin de desenvolvimento criado (`seed_dev_data`)

## Bloco 3 - Auth e componentes customizados

- [x] Endpoints JWT `login`, `refresh`, `logout` e `me`
- [x] `proxy.ts`, `auth-store.ts`, `use-auth.ts` e `use-permissions.ts`
- [x] Pagina de login integrada ao backend
- [x] 14 componentes customizados criados em `apps/web/src/components/custom/`
- [x] `src/lib/masks.ts` com mascaras e validacoes base

## Bloco 4 - Layout base

- [x] Layout principal em `apps/web/src/app/(dashboard)/layout.tsx`
- [x] Sidebar responsiva com navegacao condicional por role
- [x] Header principal com busca, filtros e sessao
- [x] Componentes shared (`StatsCard`, `DataTable`, `FilterAdvanced`, `ExportButton`, `EmptyState`)

## Validacoes executadas

- [x] `docker compose up --build -d`
- [x] `docker compose exec -T backend python manage.py showmigrations`
- [x] `docker compose exec -T backend python manage.py check`
- [x] `docker compose exec -T backend python manage.py shell -c "...Role.objects.count()..."`
- [x] `docker compose exec -T frontend pnpm --filter @abase/web type-check`
- [x] `docker compose exec -T frontend pnpm --filter @abase/web lint`
- [x] `docker compose exec -T frontend pnpm --filter @abase/web build`
- [x] `curl http://localhost:8000/api/schema/`
- [x] `curl -I http://localhost:3000`
- [x] `curl -X POST http://localhost:3000/api/auth/login ...`
- [x] `curl http://localhost:3000/api/auth/me`

## Observacoes operacionais

- `frontend` faz `pnpm install` no startup para repor links do workspace no bind mount. No primeiro boot em `/mnt/d` isso levou cerca de 4 minutos.
- Credencial de desenvolvimento validada: `admin@abase.local` / `Admin@123`
