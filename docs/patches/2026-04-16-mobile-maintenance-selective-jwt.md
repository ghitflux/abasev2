# Patch 2026-04-16: Bloqueio Temporario do App Mobile e Invalidacao Seletiva de Sessao

## Objetivo

Garantir que o modo de manutencao do app mobile:

- bloqueie novos logins do app mobile
- derrube a continuidade de sessao dos associados que ja estavam logados
- nao afete login/sessao do painel web de:
  - agentes
  - analistas
  - coordenadores
  - admins

## Problema encontrado

O kill switch mobile ja bloqueava parte das rotas do app, mas ainda havia uma brecha
no fluxo novo de autenticacao:

- `/api/v1/app/*` era bloqueado
- porem `/api/v1/auth/login/` continuava liberado para o app novo
- `/api/v1/auth/refresh/` e `/api/v1/auth/me/` tambem nao derrubavam de imediato o
  JWT ja emitido

Na pratica:

- o associado ainda conseguia logar no app mobile mesmo com
  `APP_MAINTENANCE_MODE=true`
- quem ja estava logado podia continuar com token JWT valido em alguns fluxos

## Causa raiz

O backend tratava o bloqueio de manutencao apenas nas rotas mobile legadas e nas rotas
`/api/v1/app/*`.

O app mobile novo usa:

- `/api/v1/auth/login`
- `/api/v1/auth/refresh`
- `/api/v1/auth/me`

Essas rotas nao estavam aplicando a politica de manutencao para usuarios
`ASSOCIADO` / `ASSOCIADODOIS`.

## O que foi alterado

### Backend

- [backend/apps/accounts/mobile_maintenance_policy.py](/mnt/d/apps/abasev2/abasev2/backend/apps/accounts/mobile_maintenance_policy.py)
  - nova politica isolada para:
    - identificar usuario mobile/autosservico
    - aplicar bloqueio de manutencao seletivo por papel
  - considera como usuario mobile os perfis compostos apenas por:
    - `ASSOCIADO`
    - `ASSOCIADODOIS`

- [backend/apps/accounts/authentication.py](/mnt/d/apps/abasev2/abasev2/backend/apps/accounts/authentication.py)
  - nova autenticacao JWT customizada:
    - `MaintenanceAwareJWTAuthentication`
  - apos validar o JWT, ela aplica a politica de manutencao por usuario
  - efeito pratico:
    - JWT antigo de associado mobile passa a ser recusado imediatamente durante manutencao
    - JWT de agente/admin/analista/coordenador continua valido

- [backend/config/settings/base.py](/mnt/d/apps/abasev2/abasev2/backend/config/settings/base.py)
  - `REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES` passou a usar:
    - `apps.accounts.authentication.MaintenanceAwareJWTAuthentication`

- [backend/apps/accounts/serializers.py](/mnt/d/apps/abasev2/abasev2/backend/apps/accounts/serializers.py)
  - `LoginSerializer` agora bloqueia login de associado mobile durante manutencao
  - `RefreshSerializer` agora bloqueia refresh de associado mobile durante manutencao

- [backend/apps/accounts/views.py](/mnt/d/apps/abasev2/abasev2/backend/apps/accounts/views.py)
  - `auth/me` agora bloqueia associado mobile durante manutencao
  - `register`, `forgot-password` e `reset-password` tambem respeitam o kill switch

- [backend/apps/accounts/mobile_maintenance.py](/mnt/d/apps/abasev2/abasev2/backend/apps/accounts/mobile_maintenance.py)
  - passou a reutilizar a politica nova, sem duplicar regra

### Testes

- [backend/apps/associados/tests/test_mobile_legacy_compatibility.py](/mnt/d/apps/abasev2/abasev2/backend/apps/associados/tests/test_mobile_legacy_compatibility.py)
  - o comportamento antigo "bloqueia app endpoints mas nao generic auth" deixou de ser valido
  - a cobertura foi alinhada para validar:
    - associado mobile bloqueado em manutencao
    - backoffice permanecendo liberado

## Resultado esperado

Quando `APP_MAINTENANCE_MODE=true`:

### Associado mobile

- `POST /api/v1/auth/login/` -> `503`
- `POST /api/v1/auth/refresh/` -> `503`
- `GET /api/v1/auth/me/` -> `503`
- `GET /api/v1/app/*` -> `503`

### Painel web / usuarios internos

- `AGENTE`, `ANALISTA`, `COORDENADOR`, `ADMIN` continuam:
  - fazendo login
  - usando `auth/me`
  - usando `auth/refresh`
  - sem impacto no painel web

## Validacao pratica feita localmente

No container do backend:

- associado mobile:
  - `login` antes da manutencao: `200`
  - `auth/me` depois da manutencao: `503`
  - `auth/refresh` depois da manutencao: `503`

- analista:
  - `login` antes da manutencao: `200`
  - `auth/me` depois da manutencao: `200`
  - `auth/refresh` depois da manutencao: `200`

## Importante

Nao foi feita troca de `JWT_SIGNING_KEY`.

Isso foi intencional, porque trocar a chave global de JWT derrubaria:

- app mobile
- painel web
- agentes
- coordenacao
- tesouraria
- administracao

O patch atual faz invalidaçao seletiva so para o app mobile.

## Passo a passo para o proximo deploy

### 1. Deploy

```bash
cd /app
git pull
docker compose build backend web
docker compose up -d backend web
```

### 2. Ativar manutencao mobile no servidor

No `.env` do backend:

```env
APP_MAINTENANCE_MODE=true
APP_MAINTENANCE_MESSAGE=O aplicativo esta temporariamente indisponivel para manutencao. Tente novamente em breve.
```

Aplicar:

```bash
docker compose up -d backend
```

### 3. Validacao pos-deploy

#### Validar configuracao ativa

```bash
docker compose exec -T backend printenv APP_MAINTENANCE_MODE
```

Esperado:

```bash
true
```

#### Validar status publico do app

```bash
curl -s https://SEU-DOMINIO/api/v1/app/status/ | jq
```

Esperado:

- `"maintenance": true`
- mensagem de manutencao preenchida

#### Validar bloqueio do mobile

Fazer tentativa de login com um associado no app ou via request para:

- `POST /api/v1/auth/login/`

Esperado:

- `503`
- `mobile_maintenance`

#### Validar que o web nao caiu

Testar com um usuario interno:

- login no painel web
- navegacao autenticada normal
- refresh de token funcionando

## Rollback

Para reabrir o app mobile:

```bash
# no .env
APP_MAINTENANCE_MODE=false

docker compose up -d backend
```

Nao ha migracao de banco nem alteracao irreversivel de dados neste patch.
