# Setup Local

Atualizado em 2026-03-11.

## Objetivo

Este documento descreve como iniciar a aplicação ABASE v2 localmente, quais credenciais usar para acessar o sistema e como acessar o banco MySQL.

## Pré-requisitos

- Docker e Docker Compose
- Node.js 20+
- pnpm 9+

## 1. Preparar o ambiente

Na raiz do projeto:

```bash
cp .env.example .env
docker compose down -v
docker compose build mysql
docker compose up -d mysql
docker compose up -d backend celery frontend
```

O `backend` já sobe executando:

- `python manage.py migrate`
- `python manage.py seed_dev_data`
- `python manage.py runserver 0.0.0.0:8000`

Depois confirme:

```bash
docker compose ps
```

Observações importantes:

- O dump oficial `scriptsphp/abasedb1203.sql` agora é embutido na imagem `docker/mysql/Dockerfile` e importado apenas no primeiro boot do volume `mysql_data`.
- Para restaurar o banco corretamente, recriar `mysql_data` é obrigatório. `backend`, `celery` e `frontend` só precisam subir novamente depois do `mysql` ficar saudável; não exigem recriação de volume próprio.
- Não rode `python manage.py seed_demo_data` nesse fluxo de restauração.

Serviços esperados:

- `mysql`
- `redis`
- `backend`
- `celery`
- `frontend`

## 2. Endereços locais

- Frontend: `http://localhost:3000`
- API backend: `http://localhost:8000/api/v1`
- Swagger/OpenAPI: `http://localhost:8000/api/docs/`
- Schema bruto: `http://localhost:8000/api/schema/`

## 3. Credenciais de acesso ao sistema

O comando `seed_dev_data` cria e atualiza um usuário para cada papel base do sistema.
Ele preserva hashes já existentes e só define a senha padrão em usuários de acesso recém-criados ou sem hash utilizável.

Credenciais padrão:

- `ADMIN`: `admin@abase.local` / `Admin@123`
- `AGENTE`: `agente@abase.local` / `Senha@123`
- `ANALISTA`: `analista@abase.local` / `Senha@123`
- `COORDENADOR`: `coordenador@abase.local` / `Senha@123`
- `TESOUREIRO`: `tesoureiro@abase.local` / `Senha@123`

Esses valores vêm de `.env`:

```env
DEV_ADMIN_EMAIL=admin@abase.local
DEV_ADMIN_PASSWORD=Admin@123
DEV_DEFAULT_PASSWORD=Senha@123
```

Se você alterar essas variáveis, reinicie o backend ou rode:

```bash
docker compose exec -T backend python manage.py seed_dev_data
```

Se o usuário de desenvolvimento já existir no banco restaurado, o comando preserva o hash atual. Para forçar a senha padrão novamente, recrie o usuário de desenvolvimento correspondente e reexecute o seed.

## 3.1 Seed demo completo

Para popular a aplicação com dados de exemplo de associados, contratos, esteira,
refinanciamentos, tesouraria, importação e relatórios:

```bash
docker compose exec -T backend python manage.py seed_demo_data
```

O comando é determinístico e recria apenas os registros reservados do seed demo.

## 4. Fluxo recomendado de inicialização

### Opção A: tudo via Docker

```bash
cp .env.example .env
docker compose down -v
docker compose build mysql
docker compose up -d mysql
docker compose up -d backend celery frontend
docker compose ps
```

### Opção B: validar comandos úteis

```bash
docker compose exec -T backend python manage.py check
docker compose exec -T frontend pnpm --filter @abase/web type-check
docker compose exec -T frontend pnpm --filter @abase/web test
```

## 5. Como acessar o banco de dados

### Credenciais MySQL

Do `.env.example`:

- Host externo: `127.0.0.1`
- Porta externa: `3306`
- Banco: `abase_v2`
- Usuário: `abase`
- Senha: `abase`

Connection string equivalente:

```text
mysql://abase:abase@127.0.0.1:3306/abase_v2
```

### Acesso pelo host

Com cliente MySQL instalado na máquina:

```bash
mysql -h 127.0.0.1 -P 3306 -u abase -pabase abase_v2
```

### Acesso dentro do container

```bash
docker compose exec -T mysql mysql -uabase -pabase abase_v2
```

### Acesso por GUI

Você pode usar DBeaver, DataGrip, TablePlus ou HeidiSQL com estes parâmetros:

- Host: `127.0.0.1`
- Port: `3306`
- Database: `abase_v2`
- User: `abase`
- Password: `abase`

## 6. Comandos úteis

### Backend

```bash
docker compose exec -T backend python manage.py shell
docker compose exec -T backend python manage.py migrate
docker compose exec -T backend python manage.py spectacular --file /app/schema.yaml --validate
docker compose exec -T -e DJANGO_SETTINGS_MODULE=config.settings.testing backend python manage.py test apps.importacao apps.contratos -v 2
```

### Frontend

```bash
docker compose exec -T frontend pnpm --filter @abase/web test
docker compose exec -T frontend pnpm --filter @abase/web type-check
docker compose exec -T frontend pnpm --filter @abase/web build
docker compose exec -T frontend pnpm --filter @abase/web generate:api
```

Observação:
no ambiente atual do monorepo, a forma estável de validar frontend é via container `frontend`. Os comandos acima já foram validados dessa forma.

## 7. Parar o ambiente

```bash
docker compose down
```

Se quiser remover volumes locais do banco/redis:

```bash
docker compose down -v
```

## 8. Problemas comuns

### Porta 3306 ou 3000 ocupada

Pare o serviço que já está usando a porta ou ajuste o `docker-compose.yml`.

### Usuário admin não entrou

Reexecute:

```bash
docker compose exec -T backend python manage.py seed_dev_data
```

### Banco não conectou

Confirme:

```bash
docker compose ps
docker compose logs mysql --tail=100
```

### Frontend sem dados

Confirme que o backend está saudável:

```bash
docker compose exec -T backend python manage.py check
curl http://localhost:8000/api/schema/ | head
```

## 9. Referências rápidas

- setup operacional: `docker-compose.yml`
- variáveis padrão: `.env.example`
- QA da Semana 4: `docs/QA_SEMANA_4.md`
