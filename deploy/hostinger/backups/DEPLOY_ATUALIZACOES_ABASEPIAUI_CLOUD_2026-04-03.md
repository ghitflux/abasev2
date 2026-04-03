# Deploy Objetivo de Atualizações em `abasepiaui.cloud` — 03/04/2026

## Escopo

Este roteiro é para **deploy incremental de código** no servidor atual `abasepiaui.cloud`, sem repetir importação completa de banco e sem deixar lixo operacional na VPS.

Use este fluxo para subir:

- ajustes de login e autenticação
- revisão visual do login
- correções operacionais já versionadas no Git
- documentação nova

Não use este roteiro para:

- subir dump de banco
- subir `media/` inteira
- copiar `backups/`, `dumps_legado/` ou `anexos_legado/` para a VPS

## Pré-check local

Antes do push:

```bash
cd /mnt/d/apps/abasev2/abasev2
git status --short
```

O status local deve continuar sem `media/`, `backups/`, `dumps_legado/`, `anexos_legado/` e sem artefatos temporários.

Depois:

```bash
git push origin abaseprod
```

## Pré-check no servidor

```bash
ssh deploy@72.60.58.181
cd /opt/ABASE/repo
git fetch --prune origin
git checkout abaseprod
git pull --ff-only origin abaseprod
```

Confirmar o `.env` real:

```bash
nano /opt/ABASE/env/.env.production
```

Valores mínimos a conferir neste lote:

```env
DJANGO_SETTINGS_MODULE=config.settings.production
ALLOWED_HOSTS=abasepiaui.cloud,www.abasepiaui.cloud
CSRF_TRUSTED_ORIGINS=https://abasepiaui.cloud,https://www.abasepiaui.cloud
CORS_ALLOWED_ORIGINS=https://abasepiaui.cloud,https://www.abasepiaui.cloud
NEXT_PUBLIC_API_URL=https://abasepiaui.cloud/api/v1
INTERNAL_API_URL=http://backend:8000/api/v1
JWT_ACCESS_TOKEN_LIFETIME=2880
JWT_REFRESH_TOKEN_LIFETIME=10080
```

## Deploy de código

Usar sempre o compose de produção:

```bash
cd /opt/ABASE/repo
export COMPOSE_FILE=deploy/hostinger/docker-compose.prod.yml
export ENV_FILE=/opt/ABASE/env/.env.production
```

Build apenas do que mudou:

```bash
docker compose -p abase --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build backend frontend
```

Subida controlada:

```bash
docker compose -p abase --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --no-deps --force-recreate backend
docker compose -p abase --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --no-deps --force-recreate celery
docker compose -p abase --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --no-deps --force-recreate frontend
```

Migração e checagem:

```bash
docker compose -p abase --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T backend python manage.py migrate
docker compose -p abase --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T backend python manage.py check
```

## Validação pós-deploy

```bash
curl -fsS https://abasepiaui.cloud/api/v1/health/
curl -I https://abasepiaui.cloud/login
curl -I https://abasepiaui.cloud/api/v1/auth/login/
docker ps --format 'table {{.Names}}\t{{.Status}}'
```

O esperado é:

- `backend`, `celery`, `frontend` e `nginx` em `Up`
- health check do backend respondendo `200`
- `/login` abrindo normalmente

## Mídia legada restaurada

Os arquivos restaurados localmente **não sobem pelo Git**.

Se também for necessário igualar o acervo do servidor:

- usar operação separada
- enviar só o delta de mídia restaurado
- copiar direto para `/opt/ABASE/data/media`
- não criar `/opt/ABASE/import`
- não deixar `.tar.gz`, `.sql.gz` ou manifestos soltos na VPS

Regra operacional:

- `Git`: código e documentação
- `rsync` direto: somente mídia realmente restaurada
- `nunca`: dump inteiro, `media/` inteira, `backups/`, `dumps_legado/`

## Limpeza da VPS após o deploy

Limpeza segura:

```bash
rm -f /tmp/abase_*.log /tmp/legacy_*.txt /tmp/legacy_*.json
docker image prune -f
docker builder prune -f
```

Checklist final:

- não existe `/opt/ABASE/import`
- não existe dump `.sql.gz` sobrando
- não existe tar de mídia sobrando
- `git status --short` em `/opt/ABASE/repo` está limpo

## Quando usar o roteiro de 01/04/2026

O arquivo `deploy/hostinger/backups/DEPLOY_2026-04-01.md` continua sendo a referência para:

- importação completa da base local
- promoção de acervo completo de mídia
- restauração integral de usuários e dados

Para atualização normal de código, usar este runbook de 03/04/2026.
