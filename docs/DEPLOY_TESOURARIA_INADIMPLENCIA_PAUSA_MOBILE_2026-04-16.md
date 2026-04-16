# Deploy 2026-04-16

## Escopo aplicado

### App mobile — Bloqueio temporário por API no próximo deploy
- Objetivo: impedir acesso do app mobile imediatamente pelo backend, sem afetar o painel web/admin
- Motivo do ajuste:
  - o app mobile não usa um único fluxo de autenticação
  - o app legado entra por `POST /api/login` e usa `MobileAccessToken`
  - o app mais novo usa JWT em `POST /api/v1/auth/login/`, mas consome dados em `/api/v1/app/*`
  - o bloqueio anterior em auth genérico não garantia pausa real do mobile e podia atingir o web
- Com o ajuste deste patch:
  - `APP_MAINTENANCE_MODE=true` bloqueia login, registro, reset e uso de token já emitido no fluxo legado
  - `APP_MAINTENANCE_MODE=true` bloqueia todos os endpoints `/api/v1/app/*`
  - `GET /api/v1/app/status/` continua público para informar manutenção
  - `POST /api/v1/auth/login/` e `POST /api/v1/auth/refresh/` continuam disponíveis para fluxos web/admin
  - resposta esperada no mobile bloqueado: `503 Service Unavailable` com `detail` usando `APP_MAINTENANCE_MESSAGE`

### Tesouraria — Remover da fila
- Botão "Remover da fila" (vermelho) adicionado para ADMIN/COORDENADOR em:
  - **Contratos operacionais** (`tesouraria/` — já existia, corrigido em sessão anterior)
  - **Refinanciamentos** (`tesouraria/refinanciamentos/`) — chama `RefinanciamentoService.bloquear`
  - **Pagamentos** (`tesouraria/pagamentos/`) — chama `TesourariaService.excluir_contrato_operacional`
- Cada ação exige confirmação via Dialog antes de executar
- Botão visível apenas em colunas de status pendente/aguardando/em_analise

### Tesouraria — Descartar inadimplência (baixa-manual)
- Botão "Descartar" por parcela na lista expandida de inadimplentes
- Soft-delete: seta `descartado_em` (DateTimeField) e `descartado_por` (FK User) na parcela
- Parcelas descartadas são filtradas automaticamente de `listar_parcelas_pendentes`
- **Não altera** status financeiro da parcela nem o histórico
- Migration: `contratos/0013_descartado_parcela`

### Auto-refresh inadimplentes
- Ao salvar parcela no editor avançado (`associados/[id]`), invalida a query `tesouraria-baixa-manual`
- Garante que mudanças de status `nao_descontado` apareçam imediatamente na fila

### App mobile — Kill switch de manutenção
- Endpoint público: `GET /api/v1/app/status/` → `{"maintenance": false, "message": "..."}`
- Controlado por variável de ambiente no servidor — **sem rebuild, sem publicação nas lojas**
- App já instalado mostra `MaintenanceScreen` na próxima abertura se `maintenance: true`
- No próximo deploy, além da tela de manutenção, o backend também bloqueará autenticação/uso da API mobile
- **Para pausar:**
  ```bash
  # Editar /opt/ABASE/env/.env.production:
  APP_MAINTENANCE_MODE=true
  APP_MAINTENANCE_MESSAGE=Aplicativo em manutenção. Tente novamente em breve.
  # Reiniciar só o backend:
  docker compose -p abase -f /opt/ABASE/repo/deploy/hostinger/docker-compose.prod.yml \
    --env-file /opt/ABASE/env/.env.production \
    up -d --force-recreate --no-deps backend celery
  ```
- **Para despausar:** trocar para `APP_MAINTENANCE_MODE=false` e reiniciar

### Dashboard — Filtro de período
- Filtro de competência configurável no dashboard de coordenação/admin

## Arquivos centrais

### Backend
- `backend/apps/tesouraria/views.py` — actions excluir (pagamentos) e descartar (baixa-manual)
- `backend/apps/tesouraria/services.py` — `descartar_parcela`, filtro `descartado_em__isnull=True`
- `backend/apps/refinanciamento/views.py` — action excluir (refinanciamentos)
- `backend/apps/accounts/mobile_maintenance.py` — regra central do bloqueio temporário do mobile
- `backend/apps/accounts/mobile_legacy_auth.py` — bloqueia uso de token legado durante manutenção
- `backend/apps/accounts/mobile_legacy_views.py` — bloqueia login/registro/reset do mobile legado
- `backend/apps/associados/mobile_views.py` — `AppStatusView`
- `backend/apps/associados/mobile_legacy_views.py` — bloqueia endpoints `/api/*` do app legado
- `backend/apps/associados/mobile_views.py` — bloqueia endpoints `/api/v1/app/*`
- `backend/apps/accounts/views.py` — remove dependência de manutenção mobile do auth genérico web
- `backend/apps/contratos/models.py` — campos `descartado_em`, `descartado_por` na Parcela
- `backend/apps/contratos/migrations/0013_descartado_parcela.py`
- `backend/apps/associados/migrations/0014_alter_associado_status.py`
- `backend/apps/contratos/cycle_projection.py` — `resolve_associado_mother_status`
- `backend/config/settings/base.py` — `APP_MAINTENANCE_MODE`, `APP_MAINTENANCE_MESSAGE`
- `backend/config/urls.py` — rota `api/v1/app/status/`

### Frontend web
- `apps/web/src/app/(dashboard)/tesouraria/refinanciamentos/page.tsx`
- `apps/web/src/app/(dashboard)/tesouraria/pagamentos/page.tsx`
- `apps/web/src/app/(dashboard)/tesouraria/baixa-manual/page.tsx`
- `apps/web/src/app/(dashboard)/associados/[id]/page.tsx` — invalidate `tesouraria-baixa-manual`
- `apps/web/src/components/pagamentos/pagamentos-shared.tsx` — coluna `remover_fila`
- `apps/web/src/app/(dashboard)/dashboard/page.tsx` — filtro de período

### Mobile
- `abase_mobile_new/src/app/_layout.tsx` — checa `appStatus.maintenance` na inicialização
- `abase_mobile_new/src/components/MaintenanceScreen.tsx` — tela de manutenção
- `abase_mobile_new/src/services/api/constants.ts` — endpoint `appStatus`

## Commits
- `f6e3880` — feat: remover da fila tesouraria, descartar inadimplência e pausa do app mobile
- `d7f9112` — fix: adicionar resolve_associado_mother_status e ajustes de status/relatorios

## Procedimento de deploy executado

```bash
# Push local (remote correto é abasenewv2)
git push abasenewv2 abaseprod

# No servidor
cd /opt/ABASE/repo
git pull origin abaseprod

docker compose -p abase -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  build --no-cache backend frontend

docker compose -p abase -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  up -d --force-recreate --no-deps backend celery frontend
```

## Procedimento no próximo deploy

```bash
# Push local
git push abasenewv2 abaseprod

# No servidor
cd /opt/ABASE/repo
git pull origin abaseprod

docker compose -p abase -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  build --no-cache backend

docker compose -p abase -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  up -d --force-recreate --no-deps backend celery
```

### Se a intenção for deixar o mobile pausado já após o deploy
```bash
# Editar /opt/ABASE/env/.env.production
APP_MAINTENANCE_MODE=true
APP_MAINTENANCE_MESSAGE=Aplicativo temporariamente indisponível. Tente novamente em breve.

# Recriar backend/celery para ler a nova env
docker compose -p abase -f /opt/ABASE/repo/deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  up -d --force-recreate --no-deps backend celery
```

### Se a intenção for só subir o patch e manter o mobile liberado
```bash
# Garantir no .env.production
APP_MAINTENANCE_MODE=false
```

## Validação obrigatória no servidor após o próximo deploy
- Confirmar que o web continua autenticando normalmente em `POST /api/v1/auth/login/`
- Confirmar que `GET /api/v1/app/status/` responde `maintenance: true` apenas quando a env estiver ativa
- Confirmar que `POST /api/login` retorna `503` quando `APP_MAINTENANCE_MODE=true`
- Confirmar que `GET /api/home` com token legado antigo retorna `503` quando `APP_MAINTENANCE_MODE=true`
- Confirmar que `GET /api/v1/app/me/` retorna `503` quando `APP_MAINTENANCE_MODE=true`
- Confirmar que `GET /api/v1/app/me/` volta a responder `200` após `APP_MAINTENANCE_MODE=false` e recreate do backend

## Observação operacional
- Esse bloqueio é intencionalmente restrito ao mobile
- O painel web/admin não deve ser pausado por `APP_MAINTENANCE_MODE`
- Se o servidor continuar permitindo login mobile após o próximo deploy, o ponto mais provável é container antigo sem recreate ou `.env.production` sem a variável correta

## Validação executada
- `python -m compileall` nos arquivos Python alterados — sem erros
- `tsc --noEmit` no frontend — sem erros (corrigidos 2 erros de tipo TypeScript)
- `docker ps` — todos 6 containers `(healthy)` após deploy
- `showmigrations --list` — todas migrations `[X]` aplicadas
- Health check API: `GET /api/v1/health/` retornando 200
- App status: `GET /api/v1/app/status/` retorna `{"maintenance": false, ...}`

## Limpeza de disco executada
- Removidos 6 backups de media antigos (~4.8G cada) de `/opt/ABASE/data/backups/daily/`
- Disco foi de **76% → 46%** de uso (de 73G para 44G usados em 96G)
- Manter sempre apenas o backup de media mais recente
