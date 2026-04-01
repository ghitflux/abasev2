# Importação da Base Local e do Acervo Completo no Servidor

**Tipo:** runbook operacional
**Gerado em:** 01/04/2026 18:30 (BRT)
**Ambiente de origem:** máquina local `/mnt/d/apps/abasev2/abasev2`
**Ambiente de destino:** VPS Hostinger `72.60.58.181`
**Domínio:** `abasepiaui.cloud`

---

## Objetivo

Este documento cobre o cenário em que a base **local já está validada e corrigida**
e precisa ser promovida para o servidor **junto com todo o acervo de anexos/mídia**.

Use este roteiro quando a fonte de verdade for:

- o banco local atual
- o volume local de mídia já consolidado

Não use este roteiro quando a fonte de verdade ainda for apenas o dump legado bruto.
Nesse caso, siga [importacao_legado.md](/mnt/d/apps/abasev2/abasev2/docs/importacao_legado.md).

---

## O que este runbook faz

1. exporta um dump do MySQL local
2. empacota todo o volume local de mídia
3. transfere os dois artefatos para a VPS
4. faz backup preventivo da produção
5. restaura o banco no MySQL do servidor
6. restaura o acervo completo em `/opt/ABASE/data/media` e no volume `abase_backend_media`
7. sobe novamente `backend`, `celery` e `frontend`
8. valida contagens, saúde dos containers e abertura de anexos

---

## Premissas

- o ambiente local já contém a base final correta
- o volume local de mídia contém todos os anexos e comprovantes válidos
- o servidor já está com a stack Hostinger operacional em `/opt/ABASE/repo`
- o compose de produção usado é [docker-compose.prod.yml](/mnt/d/apps/abasev2/abasev2/deploy/hostinger/docker-compose.prod.yml)

---

## Caminhos usados

### Origem local

- repositório: `/mnt/d/apps/abasev2/abasev2`
- dump local gerado: `backups/server_seed_<timestamp>/local_db.sql.gz`
- mídia local gerada: `backups/server_seed_<timestamp>/local_media.tar.gz`

### Destino no servidor

- repositório: `/opt/ABASE/repo`
- env: `/opt/ABASE/env/.env.production`
- staging de importação: `/opt/ABASE/import/server_seed_<timestamp>`
- mídia persistente: `/opt/ABASE/data/media`

---

## Janela recomendada

Agende janela de manutenção.

Durante o restore:

- o `mysql` precisa ficar ativo
- `backend`, `celery` e `frontend` devem ficar parados para evitar escrita concorrente

---

## Etapa 1 — Exportar a base local

No ambiente local, a partir da raiz do repositório:

```bash
cd /mnt/d/apps/abasev2/abasev2

EXPORT_TS="$(date +%Y%m%d_%H%M%S)"
EXPORT_DIR="backups/server_seed_${EXPORT_TS}"
mkdir -p "${EXPORT_DIR}"

docker compose exec -T mysql sh -lc \
  'mysqldump --no-tablespaces -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' \
  > "${EXPORT_DIR}/local_db.sql"

gzip "${EXPORT_DIR}/local_db.sql"
```

Resultado esperado:

- arquivo `${EXPORT_DIR}/local_db.sql.gz`

---

## Etapa 2 — Empacotar o acervo local completo

### Método preferido: volume Docker oficial

Confirme primeiro o nome do volume local:

```bash
docker volume ls | grep backend_media
```

No ambiente local atual, o nome esperado costuma ser:

- `abase-v2_backend_media`

Empacote:

```bash
docker run --rm \
  -v abase-v2_backend_media:/source:ro \
  -v "$(pwd)/${EXPORT_DIR}:/backup" \
  alpine sh -lc 'cd /source && tar czf /backup/local_media.tar.gz .'
```

### Manifesto opcional para conferência

```bash
docker run --rm \
  -v abase-v2_backend_media:/source:ro \
  alpine sh -lc 'cd /source && find . -type f | sort' \
  > "${EXPORT_DIR}/local_media_manifest.txt"

sha256sum "${EXPORT_DIR}/local_db.sql.gz" "${EXPORT_DIR}/local_media.tar.gz" \
  > "${EXPORT_DIR}/checksums.sha256"
```

Resultado esperado:

- `${EXPORT_DIR}/local_media.tar.gz`
- opcionalmente:
  - `${EXPORT_DIR}/local_media_manifest.txt`
  - `${EXPORT_DIR}/checksums.sha256`

---

## Etapa 3 — Capturar contagens da base local

Isso facilita a validação final no servidor.

```bash
docker compose exec -T backend python manage.py shell -c "
from apps.associados.models import Associado
from apps.contratos.models import Contrato, Parcela
from apps.importacao.models import ArquivoRetorno
print({
    'associados': Associado.objects.count(),
    'contratos': Contrato.objects.count(),
    'parcelas': Parcela.objects.count(),
    'arquivos_retorno': ArquivoRetorno.objects.count(),
})
"
```

Guarde esse resultado junto do pacote exportado.

---

## Etapa 4 — Transferir os artefatos para a VPS

No host local:

```bash
SERVER_DIR="/opt/ABASE/import/server_seed_${EXPORT_TS}"

ssh root@72.60.58.181 "mkdir -p ${SERVER_DIR}"

scp "${EXPORT_DIR}/local_db.sql.gz" \
  root@72.60.58.181:"${SERVER_DIR}/"

scp "${EXPORT_DIR}/local_media.tar.gz" \
  root@72.60.58.181:"${SERVER_DIR}/"

scp "${EXPORT_DIR}/checksums.sha256" \
  root@72.60.58.181:"${SERVER_DIR}/" 2>/dev/null || true

scp "${EXPORT_DIR}/local_media_manifest.txt" \
  root@72.60.58.181:"${SERVER_DIR}/" 2>/dev/null || true
```

Se o acervo estiver muito grande e `scp` estiver lento, pode usar:

```bash
rsync -ah --info=progress2 "${EXPORT_DIR}/" \
  root@72.60.58.181:"${SERVER_DIR}/"
```

---

## Etapa 5 — Validar integridade dos arquivos na VPS

No servidor:

```bash
cd "/opt/ABASE/import/server_seed_${EXPORT_TS}"
ls -lh
sha256sum -c checksums.sha256
```

Se `checksums.sha256` não existir, pelo menos valide:

```bash
gzip -t local_db.sql.gz
tar -tzf local_media.tar.gz > /dev/null
```

---

## Etapa 6 — Backup preventivo da produção

No servidor:

```bash
cd /opt/ABASE/repo
bash deploy/hostinger/scripts/backup_now.sh
```

Esse passo gera backup do banco, mídia e env antes da sobrescrita.

---

## Etapa 7 — Parar a camada de aplicação

No servidor:

```bash
cd /opt/ABASE/repo

docker stop abase-frontend-prod abase-backend-prod abase-celery-prod
```

Confirme:

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}'
```

Esperado:

- `abase-mysql-prod`, `abase-redis-prod` e `abase-nginx-prod` continuam ativos
- `abase-backend-prod`, `abase-celery-prod` e `abase-frontend-prod` ficam parados

---

## Etapa 8 — Restaurar o banco local no MySQL do servidor

No servidor:

```bash
cd /opt/ABASE/repo
source /opt/ABASE/env/.env.production

zcat "/opt/ABASE/import/server_seed_${EXPORT_TS}/local_db.sql.gz" \
  | docker compose -p abase --env-file /opt/ABASE/env/.env.production \
      -f deploy/hostinger/docker-compose.prod.yml \
      exec -T mysql \
      mysql -u"${DATABASE_USER}" -p"${DATABASE_PASSWORD}" "${DATABASE_NAME}"
```

Observações:

- esse passo substitui o conteúdo lógico do banco de produção pelo banco local exportado
- como o `backend` está parado, não há escrita concorrente durante o restore

---

## Etapa 9 — Restaurar o acervo completo no servidor

Use o script oficial do projeto:

```bash
cd /opt/ABASE/repo
bash deploy/hostinger/scripts/restore_files.sh \
  "/opt/ABASE/import/server_seed_${EXPORT_TS}/local_media.tar.gz"
```

Esse script:

- extrai o `tar.gz`
- copia para o volume Docker `abase_backend_media`
- replica também para `/opt/ABASE/data/media`

---

## Etapa 10 — Subir novamente backend, celery e frontend

No servidor:

```bash
cd /opt/ABASE/repo

docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml \
  up -d backend

docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml \
  up -d celery

docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml \
  up -d frontend
```

Se quiser recriar explicitamente:

```bash
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml \
  up -d --force-recreate backend celery frontend
```

---

## Etapa 11 — Checks pós-restore

### Saúde dos containers

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

Esperado:

- `abase-backend-prod` em `healthy`
- `abase-celery-prod` em execução
- `abase-frontend-prod` em execução

### Checks Django

```bash
cd /opt/ABASE/repo

docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml \
  exec -T backend python manage.py check
```

### Contagens principais

Rode no servidor e compare com a saída capturada na etapa 3:

```bash
cd /opt/ABASE/repo

docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml \
  exec -T backend python manage.py shell -c "
from apps.associados.models import Associado
from apps.contratos.models import Contrato, Parcela
from apps.importacao.models import ArquivoRetorno
print({
    'associados': Associado.objects.count(),
    'contratos': Contrato.objects.count(),
    'parcelas': Parcela.objects.count(),
    'arquivos_retorno': ArquivoRetorno.objects.count(),
})
"
```

### Verificação de mídia

```bash
find /opt/ABASE/data/media -type f | wc -l
du -sh /opt/ABASE/data/media
```

### Testes HTTP mínimos

```bash
curl -I https://abasepiaui.cloud/login
curl -I https://abasepiaui.cloud/api/v1/auth/login/
curl -I https://abasepiaui.cloud/api/media/
```

Interpretação:

- `/login` deve responder `200`
- `/api/v1/auth/login/` deve responder `405` em `GET`
- `/api/media/...` deve responder normalmente para arquivos reais

---

## Etapa 12 — Validação funcional recomendada

Depois da restauração:

- autenticar no painel administrativo
- abrir alguns associados
- validar anexos históricos
- abrir `/tesouraria`
- validar `Novos Contratos`, `Pagamentos` e `Renovações`
- abrir um associado com origem mobile e confirmar o badge
- validar login e bootstrap do app mobile se houver conta de teste

---

## Rollback

Se algo falhar após o restore:

### Banco

Use o dump produzido pelo backup preventivo:

```bash
cd /opt/ABASE/repo
ls -lh /opt/ABASE/data/backups/daily/db_*.sql.gz | tail
bash deploy/hostinger/scripts/restore_db.sh /opt/ABASE/data/backups/daily/<arquivo>.sql.gz
```

### Mídia

```bash
cd /opt/ABASE/repo
ls -lh /opt/ABASE/data/backups/daily/media_*.tar.gz | tail
bash deploy/hostinger/scripts/restore_files.sh /opt/ABASE/data/backups/daily/<arquivo>.tar.gz
```

Depois:

```bash
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml \
  up -d backend celery frontend
```

---

## Observações finais

- este runbook promove o **estado local atual** para a produção
- ele não reaplica o dump legado bruto; ele replica o banco e a mídia já consolidados localmente
- dumps, backups e manifestos grandes não devem ser commitados no git
- se o objetivo for reexecutar a restauração legada no servidor usando o dump e `anexos_legado`, use [importacao_legado.md](/mnt/d/apps/abasev2/abasev2/docs/importacao_legado.md)

---

**Preparado por:** Codex
**Status:** pronto para uso manual
