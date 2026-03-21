# PRODUCTION AUDIT — ABASE v2
**Data**: 2026-03-17
**Branch de produção**: abaseprod
**Domínio**: abasepiaui.cloud
**VPS**: 72.60.58.181 (Hostinger Ubuntu 24.04 LTS)

---

## STACK IDENTIFICADA

| Componente | Tecnologia | Versão |
|-----------|-----------|--------|
| Backend | Django | 6.0.2 |
| Frontend | Next.js | 16.1.6 |
| Banco de Dados | MySQL | 8.0 |
| Cache/Broker | Redis | 7-alpine |
| Worker | Celery | 5.4.0 |
| WSGI | Gunicorn | 23.0.0 |
| Monorepo | pnpm workspaces | 9.15.0 |
| Container | Docker + Compose | — |

---

## A) DEVE IR PARA A VPS

### Backend Django
- `backend/` — aplicação Django completa
- `backend/requirements/` — dependências Python
- `backend/config/` — settings, URLs, WSGI, ASGI, Celery
- `backend/apps/` — apps do Django (accounts, associados, contratos, etc.)
- `backend/core/` — modelos/helpers core
- `backend/manage.py` — CLI do Django
- **NÃO** incluir `backend/media/` no git (montado como volume Docker)
- **NÃO** incluir `backend/staticfiles/` (gerado via collectstatic)
- **NÃO** incluir `backend/.pytest_cache/`, `backend/__pycache__/`

### Frontend Next.js
- `apps/web/` — aplicação Next.js completa (sem node_modules, .next)
- `packages/shared-types/` — tipos compartilhados (importado pelo frontend)
- `packages/tsconfig/` — config TypeScript compartilhada
- `packages/eslint-config/` — ESLint compartilhado
- `pnpm-workspace.yaml` — definição do workspace monorepo
- `package.json` — root pnpm
- `.npmrc` (se existir) — configuração do npm/pnpm

### Infraestrutura Docker
- `docker/` — Dockerfiles de backend e frontend
- `deploy/` — toda a estrutura criada nesta branch
- `.dockerignore` — regras de exclusão do build Docker

---

## B) NÃO DEVE IR PARA A VPS

| Diretório/Arquivo | Motivo |
|-------------------|--------|
| `abase_mobile/` | App mobile legado, sem dependência do backend web |
| `anexos_legado/` | Arquivos históricos locais, sem uso em runtime |
| `backups/` | Backups locais de desenvolvimento |
| `pdfs/` | PDFs locais, sem referência no código de produção |
| `scriptsphp/` | Scripts PHP legados, incluindo `abasedb1203.sql` (seed dev) |
| `conexao/` | Arquivos de conexão PHP legados |
| `iniciar-local.bat` | Script Windows de desenvolvimento |
| `.env` | Credenciais de desenvolvimento |
| `node_modules/` | Dependências recriadas no build |
| `apps/web/node_modules/` | Idem |
| `apps/web/.next/` | Artefatos de build (recriados no container) |
| `.venv/` | Ambiente virtual Python (recriado no container) |
| `backend/staticfiles/` | Gerado via `collectstatic` na VPS |
| `backend/.pytest_cache/` | Cache de testes |
| `.pytest_cache/` | Cache de testes |
| `.mypy_cache/` | Cache de type checking |
| `.turbo/` | Cache de build Turbopack |
| `node_modules_drvfs_failed_20260312165530` | Artefato de falha de instalação |
| `docs/` | Documentação sem uso em runtime (exceto deploy/) |

---

## BANCO DE DADOS REAL: MySQL 8.0

**Decisão**: Manter MySQL 8.0.

**Justificativa**:
1. O código possui `enforce_mysql_only()` em `config/runtime.py` que lança `ImproperlyConfigured` se outro banco for usado.
2. Todas as migrations foram escritas para MySQL (charset utf8mb4, ENGINE específicos).
3. Trocar de banco exigiria reescrever migrations, configuração e possivelmente código.

**Configuração de produção**:
```
DATABASE_HOST=mysql          # nome do serviço Docker
DATABASE_PORT=3306
DATABASE_NAME=abase_v2       # manter o mesmo nome
DATABASE_USER=abase
DATABASE_PASSWORD=<SENHA_FORTE>
```

---

## REDIS E CELERY: NECESSÁRIOS

**Decisão**: Redis e Celery são obrigatórios em produção.

**Justificativa**:
1. `django-celery-results` está em INSTALLED_APPS — migration obrigatória.
2. Há tarefas assíncronas configuradas no Celery (`config/celery.py`).
3. Em desenvolvimento, Celery roda em modo síncrono (`CELERY_TASK_ALWAYS_EAGER = True`), mascarando dependências reais.
4. Sem Celery worker, tarefas agendadas e background jobs não funcionarão.

---

## MEDIA, UPLOADS, ANEXOS E COMPROVANTES

| Tipo | Caminho no Container | Volume Docker |
|------|---------------------|---------------|
| Uploads gerais | `/app/media/` | `backend_media` |
| Fotos de perfil | `/app/media/fotos/` | `backend_media` |
| Comprovantes | `/app/media/comprovantes/` | `backend_media` |
| Anexos | `/app/media/anexos/` | `backend_media` |
| Documentos | `/app/media/documentos/` | `backend_media` |
| Static (gerado) | `/app/staticfiles/` | `backend_static` |

**Configuração Django**:
```python
MEDIA_ROOT = BASE_DIR / "media"    # /app/media
MEDIA_URL = "/media/"
STATIC_ROOT = BASE_DIR / "staticfiles"  # /app/staticfiles
STATIC_URL = "/static/"
```

---

## VARIÁVEIS DE AMBIENTE OBRIGATÓRIAS PARA PRODUÇÃO

```dotenv
# Django
DJANGO_SETTINGS_MODULE=config.settings.production
SECRET_KEY=<gerar-com-python-secrets>
DEBUG=False
ALLOWED_HOSTS=abasepiaui.cloud,www.abasepiaui.cloud
CSRF_TRUSTED_ORIGINS=https://abasepiaui.cloud,https://www.abasepiaui.cloud

# MySQL
DATABASE_NAME=abase_v2
DATABASE_USER=abase
DATABASE_PASSWORD=<SENHA_FORTE>
DATABASE_HOST=mysql
DATABASE_PORT=3306

# Redis / Celery
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# JWT
JWT_ACCESS_TOKEN_LIFETIME=15
JWT_REFRESH_TOKEN_LIFETIME=10080

# Frontend
NEXT_PUBLIC_API_URL=https://abasepiaui.cloud/api/v1
INTERNAL_API_URL=http://backend:8000/api/v1
NODE_ENV=production
```

---

## PROBLEMAS CRÍTICOS IDENTIFICADOS (CORRIGIDOS NESTA BRANCH)

| Problema | Arquivo | Solução |
|----------|---------|---------|
| `wsgi.py` usa settings de dev | `backend/config/wsgi.py` | Usar env var `DJANGO_SETTINGS_MODULE` |
| `asgi.py` usa settings de dev | `backend/config/asgi.py` | Usar env var `DJANGO_SETTINGS_MODULE` |
| `docker-compose.yml` roda `seed_dev_data` | `docker-compose.yml` | Novo `docker-compose.prod.yml` sem seed |
| Frontend usa `next dev` | `docker/frontend/Dockerfile` | Novo `Dockerfile.frontend.prod` com `next build && next start` |
| MySQL init importa SQL dev | `docker/mysql/` | Init limpo em produção |
| Secret key padrão | `.env` | Exigir variável de ambiente obrigatória |

---

## ESTRATÉGIA DE SSL

**Escolha**: Nginx em container com Certbot via ACME HTTP-01.

**Justificativa**:
1. Compatível com Docker Manager da Hostinger (compose portável).
2. Nginx como único serviço exposto publicamente (portas 80 e 443).
3. Backend e frontend acessíveis apenas via rede Docker interna.
4. Certbot emite e renova certificado automaticamente.

---

## SERVIÇOS DOCKER DE PRODUÇÃO

| Serviço | Exposição | Justificativa |
|---------|-----------|---------------|
| `nginx` | 80, 443 → público | Borda pública, proxy reverso, SSL |
| `backend` | interno apenas | API Django via Gunicorn |
| `celery` | interno apenas | Worker de tarefas assíncronas |
| `frontend` | interno apenas | Next.js via node server |
| `mysql` | interno apenas | Banco de dados MySQL 8.0 |
| `redis` | interno apenas | Cache e broker Celery |
