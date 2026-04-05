# Runbook Único de Setup, Hardening, Backup, Restore e Deploy

> Arquivo autoritativo para `abasepiaui.com` (produção).
> Referências a `abasepiaui.cloud` neste documento ficam apenas como histórico operacional.
> Este documento substitui os demais `.md` removidos de `deploy/`.

## 1. Escopo e regra operacional

Este runbook cobre:

- setup inicial da VPS de produção
- hardening do host e protocolo mínimo anti-invasão
- deploy incremental de código
- restore completo de banco + mídia
- promoção completa de base para produção
- histórico do último deploy validado
- plano do próximo deploy em `abasepiaui.com`
- ajuste do app mobile para a API final em `abasepiaui.com`
- preparo do build iOS via Expo EAS

Regras fixas:

- produção oficial: `https://abasepiaui.com`
- branch operacional: `abaseprod`
- stack pública: `nginx`, `frontend`, `backend`, `celery`, `mysql`, `redis`
- nenhum dump, tarball, backup, `media/`, `anexos_legado/` ou `dumps_legado/` fica dentro de `/opt/ABASE/repo`
- toda operação destrutiva exige backup imediatamente antes
- nunca aplicar atualização cega de containers em produção; automático só para segurança do host, assinatura antimalware e renovação TLS

## 2. Inventário de ambientes

### Produção

- domínio: `abasepiaui.com`
- uso: tráfego real, web oficial, API oficial, app mobile oficial
- política: deploy controlado, sem auto-rebuild cego

### Homologação histórica

- domínio: `abasepiaui.cloud`
- uso: referência histórica de ensaio de deploy, restore completo e validações
- política atual: não é mais alvo operacional deste runbook

## 3. Layout obrigatório na VPS

```text
/opt/ABASE/
  repo/                         # checkout git limpo
  env/.env.production           # segredos
  logs/                         # logs operacionais
  data/
    db/                         # persistência MySQL
    redis/                      # persistência Redis
    media/                      # anexos, comprovantes, uploads
    static/                     # collectstatic
    certbot/
      conf/
      www/
    backups/
      daily/
      weekly/
      monthly/
  import/
    <release>/                  # staging temporário de dumps e tarballs
```

Diretórios que não devem existir dentro de `/opt/ABASE/repo`:

- dumps SQL
- arquivos `.tar.gz` de mídia
- backups manuais
- cópias de `media/`
- relatórios temporários de importação

## 4. Bootstrap da VPS de produção

Executar como `root` na VPS nova:

```bash
apt update && apt upgrade -y
timedatectl set-timezone America/Fortaleza
apt install -y \
  curl git ufw fail2ban ca-certificates gnupg lsb-release unzip \
  apt-transport-https software-properties-common netcat-openbsd \
  unattended-upgrades apt-listchanges needrestart \
  clamav clamav-freshclam rkhunter aide debsums
```

### Usuário de deploy

```bash
adduser deploy
usermod -aG sudo deploy
mkdir -p /home/deploy/.ssh
cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys
```

### Docker

```bash
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
| tee /etc/apt/sources.list.d/docker.list > /dev/null
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable docker --now
usermod -aG docker deploy
```

### Firewall e SSH

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

Ajustes obrigatórios em `/etc/ssh/sshd_config`:

- `PermitRootLogin no`
- `PasswordAuthentication no`
- `PubkeyAuthentication yes`
- `MaxAuthTries 3`
- `X11Forwarding no`

Depois:

```bash
systemctl restart ssh
systemctl enable fail2ban --now
```

### Diretórios

```bash
mkdir -p /opt/ABASE/{repo,env,logs,import}
mkdir -p /opt/ABASE/data/{db,redis,media,static,backups/{daily,weekly,monthly},certbot/{conf,www}}
chown -R deploy:deploy /opt/ABASE
chmod 750 /opt/ABASE /opt/ABASE/env /opt/ABASE/logs /opt/ABASE/import
chmod 770 /opt/ABASE/data/media /opt/ABASE/data/static
```

## 5. Hardening obrigatório do host

### 5.1 Atualizações automáticas seguras

Aplicar automático apenas para segurança do host. Não habilitar auto-rebuild automático do app em produção.

```bash
cat >/etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
APT::Periodic::Verbose "1";
EOF

dpkg-reconfigure -plow unattended-upgrades
systemctl enable unattended-upgrades --now
```

Política:

- host: atualização automática de segurança habilitada
- certbot: renovação automática habilitada
- assinaturas antimalware: atualização automática habilitada
- imagens Docker: validar primeiro em ambiente local controlado e só então promover para produção
- não usar `watchtower` ou equivalente em produção

### 5.2 Antimalware e integridade

Inicialização:

```bash
freshclam || true
rkhunter --update
rkhunter --propupd
aideinit
cp /var/lib/aide/aide.db.new /var/lib/aide/aide.db
systemctl enable clamav-freshclam --now
```

Rotina semanal recomendada:

```bash
cat >/usr/local/sbin/abase-host-scan.sh <<'EOF'
#!/bin/bash
set -euo pipefail
LOG_DIR=/var/log/abase-security
mkdir -p "$LOG_DIR"
clamscan -ri --exclude-dir='^/opt/ABASE/data/media$' /opt/ABASE /etc /usr/local/bin >> "$LOG_DIR/clamav.log" 2>&1 || true
rkhunter --check --skip-keypress >> "$LOG_DIR/rkhunter.log" 2>&1 || true
aide --check >> "$LOG_DIR/aide.log" 2>&1 || true
EOF
chmod 700 /usr/local/sbin/abase-host-scan.sh
```

Cron:

```bash
cat >/etc/cron.d/abase-host-scan <<'EOF'
20 4 * * 0 root /usr/local/sbin/abase-host-scan.sh
EOF
```

Se houver detecção:

- isolar host da internet se o alerta for crítico
- coletar `docker ps`, `ss -tulpn`, `last -a`, `journalctl -xe`, `/var/log/auth.log`
- rodar backup imediato só de evidência, sem sobrescrever backups saudáveis
- trocar `SECRET_KEY`, senhas de MySQL, credenciais SSH e tokens de CI após contenção
- rebuild completo da stack a partir de código confiável

### 5.3 Protocolo anti-SQL injection e anti-intrusão

Checklist obrigatório antes de promover qualquer release:

- MySQL e Redis continuam sem `ports:` publicados no host
- `DEBUG=False`
- `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` e `CORS_ALLOWED_ORIGINS` restritos ao domínio do ambiente
- apenas o proxy Nginx expõe `80/443`
- nenhum endpoint administrativo ou de debug exposto publicamente além do necessário
- revisão manual de qualquer diff com SQL cru, `cursor.execute`, `RawSQL`, interpolação de query, upload ou importação
- scripts de restore/importação executados só a partir de arquivos revisados e versionados
- não reutilizar dumps recebidos sem checksum e conferência de origem
- manter `client_max_body_size` apenas no tamanho estritamente necessário
- invalidar sessões e rotacionar segredos se houver suspeita de abuso

Medidas adicionais já esperadas na stack:

- Django ORM e queries parametrizadas por padrão
- backend, frontend, MySQL e Redis isolados em rede Docker privada
- cabeçalhos de segurança aplicados no `nginx.conf`
- autenticação web via cookies httpOnly e proxy de API no frontend

## 6. Clonagem do projeto e env de produção

```bash
cd /opt/ABASE
git clone -b abaseprod https://github.com/ghitflux/abasenewv2.git repo
cp /opt/ABASE/repo/deploy/hostinger/.env.production.example /opt/ABASE/env/.env.production
chmod 600 /opt/ABASE/env/.env.production
```

Preencher `/opt/ABASE/env/.env.production` com:

```env
COMPOSE_PROJECT_NAME=abase
DJANGO_SETTINGS_MODULE=config.settings.production
SECRET_KEY=<gerar com python3 -c "import secrets; print(secrets.token_urlsafe(64))">
DEBUG=False

ALLOWED_HOSTS=abasepiaui.com,www.abasepiaui.com
CSRF_TRUSTED_ORIGINS=https://abasepiaui.com,https://www.abasepiaui.com
CORS_ALLOWED_ORIGINS=https://abasepiaui.com,https://www.abasepiaui.com

DATABASE_NAME=abase_v2
DATABASE_USER=abase
DATABASE_PASSWORD=<senha forte>
DATABASE_HOST=mysql
DATABASE_PORT=3306

MYSQL_ROOT_PASSWORD=<senha forte>
MYSQL_DATABASE=abase_v2
MYSQL_USER=abase
MYSQL_PASSWORD=<senha forte>

REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

JWT_ACCESS_TOKEN_LIFETIME=2880
JWT_REFRESH_TOKEN_LIFETIME=10080

NEXT_PUBLIC_API_URL=https://abasepiaui.com/api/v1
INTERNAL_API_URL=http://backend:8000/api/v1
DOMAIN=abasepiaui.com
CERTBOT_EMAIL=<email_operacional>
```

### 6.1 Distribuição recomendada de memória e workers

Baseline operacional recomendado para `abasepiaui.com`:

- `backend`: `768m`
- `celery`: `1280m`
- `frontend`: `384m`
- `nginx`: `128m`

Runtime recomendado:

- `GUNICORN_WORKERS=3`
- `GUNICORN_THREADS=2`
- `GUNICORN_TIMEOUT=180`
- `GUNICORN_KEEPALIVE=10`
- `GUNICORN_MAX_REQUESTS=800`
- `GUNICORN_MAX_REQUESTS_JITTER=80`
- `CELERY_CONCURRENCY=1`
- `CELERY_PREFETCH_MULTIPLIER=1`
- `CELERY_MAX_TASKS_PER_CHILD=20`
- `FRONTEND_NODE_MAX_OLD_SPACE_MB=256`

Objetivo dessa distribuição:

- manter o backend responsivo nas rotas mais lentas sem voltar ao consumo antigo dos 4 workers
- reservar mais memória real para o `celery`, que absorve importações e saneamentos pesados
- impedir crescimento descontrolado do frontend Node
- manter o `nginx` previsível e pequeno

Ajuste fino recomendado:

- se a VPS pressionar memória, reduzir primeiro `GUNICORN_WORKERS` de `3` para `2`
- não subir `CELERY_CONCURRENCY` sem medir RAM real durante importação pesada
- manter `CELERY_MAX_TASKS_PER_CHILD` para reciclar processos longos

## 7. Ajustes de domínio antes do primeiro deploy de produção

Arquivos que precisam refletir o domínio final:

- `deploy/hostinger/nginx/nginx.conf`
- `deploy/hostinger/docker-compose.prod.yml`
- `deploy/hostinger/.env.production.example`

Trocas mínimas para produção:

- `abasepiaui.cloud` → `abasepiaui.com`
- `www.abasepiaui.cloud` → `www.abasepiaui.com`
- `https://abasepiaui.cloud/api/v1` → `https://abasepiaui.com/api/v1`

`abasepiaui.cloud` permanece apenas como referência histórica.

## 8. TLS e renovação automática

### Certificado temporário

Se o DNS ainda não propagou:

```bash
mkdir -p /opt/ABASE/data/certbot/conf/live/abasepiaui.com
openssl req -x509 -nodes -newkey rsa:4096 -days 365 \
  -keyout /opt/ABASE/data/certbot/conf/live/abasepiaui.com/privkey.pem \
  -out /opt/ABASE/data/certbot/conf/live/abasepiaui.com/fullchain.pem \
  -subj "/CN=abasepiaui.com"
cp /opt/ABASE/data/certbot/conf/live/abasepiaui.com/fullchain.pem \
  /opt/ABASE/data/certbot/conf/live/abasepiaui.com/chain.pem
```

### Certificado real

```bash
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f /opt/ABASE/repo/deploy/hostinger/docker-compose.prod.yml up -d nginx

docker run --rm \
  -v /opt/ABASE/data/certbot/conf:/etc/letsencrypt \
  -v /opt/ABASE/data/certbot/www:/var/www/certbot \
  certbot/certbot certonly --webroot \
  --webroot-path=/var/www/certbot \
  --email <email_operacional> --agree-tos --no-eff-email \
  -d abasepiaui.com -d www.abasepiaui.com
```

Renovação automática:

```bash
cat >/etc/cron.d/abase-certbot <<'EOF'
10 2 * * * root docker run --rm \
  -v /opt/ABASE/data/certbot/conf:/etc/letsencrypt \
  -v /opt/ABASE/data/certbot/www:/var/www/certbot \
  certbot/certbot renew --webroot -w /var/www/certbot --quiet && \
  docker exec abase-nginx-prod nginx -s reload
EOF
```

## 9. Primeira subida da stack de produção

```bash
cd /opt/ABASE/repo
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml build backend frontend celery
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml up -d
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml exec -T backend python manage.py migrate
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml exec -T backend python manage.py check
docker exec abase-nginx-prod nginx -t
docker exec abase-nginx-prod nginx -s reload
```

Validação mínima:

```bash
curl -fsS https://abasepiaui.com/api/v1/health/
curl -I https://abasepiaui.com/login
curl -I https://abasepiaui.com/api/v1/auth/login/
```

## 10. Deploy incremental de código

Fluxo oficial:

```bash
cd /opt/ABASE/repo
bash deploy/hostinger/scripts/deploy_prod.sh
```

O script:

- faz backup preventivo
- atualiza `abaseprod`
- rebuilda `backend`, `celery` e `frontend`
- recria a stack
- valida saúde básica

Pós-deploy manual obrigatório:

- login web e logout
- upload e abertura de anexo
- importação de arquivo retorno com dry-run
- gestão de usuários e redistribuição de carteira
- abertura de contratos com comprovantes

### 10.1 Gate técnico antes do deploy oficial

Antes de qualquer promoção para `abasepiaui.com`, executar e registrar:

```bash
docker compose run --rm backend-tools \
  python manage.py test \
  apps.accounts apps.associados apps.contratos apps.esteira \
  apps.financeiro apps.importacao apps.refinanciamento apps.relatorios apps.tesouraria

docker compose run --rm backend-tools \
  python manage.py test \
  apps.importacao.tests.test_reconciliacao \
  apps.importacao.tests.test_services \
  apps.importacao.tests.test_reimport_staged_return_files \
  apps.esteira.tests.test_analise

docker compose run --rm frontend sh -lc \
  "pnpm --filter @abase/web test -- --runInBand --runTestsByPath \
  src/app/'(dashboard)'/importacao/page.test.tsx \
  src/lib/navigation.test.ts"

docker compose run --rm frontend sh -lc \
  "pnpm --filter @abase/web type-check"
```

Regra operacional:

- a suíte completa do backend por app label é o gate bloqueador de release
- a bateria focada em `importacao`/`esteira` e o `type-check` do frontend são obrigatórios, mas não substituem a suíte completa
- se a suíte completa falhar, o deploy oficial fica bloqueado até correção ou aprovação explícita de risco

## 11. Backup e restore

### Backup manual

```bash
cd /opt/ABASE/repo
bash deploy/hostinger/scripts/backup_now.sh
```

Retenção atual:

- 7 diários
- 4 semanais
- 3 mensais

### Restore apenas do banco

```bash
bash /opt/ABASE/repo/deploy/hostinger/scripts/restore_db.sh \
  /opt/ABASE/data/backups/daily/db_<timestamp>.sql.gz
```

### Restore apenas da mídia

```bash
bash /opt/ABASE/repo/deploy/hostinger/scripts/restore_files.sh \
  /opt/ABASE/data/backups/daily/media_<timestamp>.tar.gz
```

## 12. Protocolo legado de promoção completa para homologação `abasepiaui.cloud`

Use este fluxo apenas como referência histórica quando for necessário consultar a antiga promoção completa para `.cloud`.

### 12.1 Fonte de verdade

Escolher apenas uma origem:

- produção `abasepiaui.com`, ou
- ambiente local validado e mais recente

Nunca misturar duas origens no mesmo ciclo de importação.

### 12.2 Gerar artefatos na origem

Banco:

```bash
docker compose exec -T mysql sh -lc \
  'mysqldump --no-tablespaces -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' \
  > /tmp/local_db.sql
gzip -f /tmp/local_db.sql
```

Mídia:

```bash
docker run --rm \
  -v abase-v2_backend_media:/source:ro \
  -v /tmp:/backup \
  alpine sh -lc 'cd /source && tar czf /backup/local_media.tar.gz .'
```

Checksums:

```bash
sha256sum /tmp/local_db.sql.gz /tmp/local_media.tar.gz > /tmp/checksums.sha256
```

### 12.3 Transferir para a homologação

No destino, usar staging fora do repositório:

```bash
RELEASE_TS="$(date +%Y%m%d_%H%M%S)"
SERVER_DIR="/opt/ABASE/import/release_${RELEASE_TS}"
mkdir -p "${SERVER_DIR}"
```

Transferir:

```bash
scp /tmp/local_db.sql.gz root@<IP_CLOUD>:"${SERVER_DIR}/"
scp /tmp/local_media.tar.gz root@<IP_CLOUD>:"${SERVER_DIR}/"
scp /tmp/checksums.sha256 root@<IP_CLOUD>:"${SERVER_DIR}/"
```

### 12.4 Backup preventivo da homologação

```bash
cd /opt/ABASE/repo
bash deploy/hostinger/scripts/backup_now.sh
```

Opcional, se for preciso preservar usuários exclusivos da homologação:

- exportar `accounts_user` antes da importação
- restaurar os usuários desejados após o import

### 12.5 Validar integridade dos artefatos

```bash
cd "${SERVER_DIR}"
sha256sum -c checksums.sha256
gzip -t local_db.sql.gz
tar -tzf local_media.tar.gz >/dev/null
```

### 12.6 Parar camada de aplicação

```bash
docker stop abase-frontend-prod abase-backend-prod abase-celery-prod
```

MySQL, Redis e Nginx permanecem ativos.

### 12.7 Importar banco completo

```bash
source /opt/ABASE/env/.env.production
zcat "${SERVER_DIR}/local_db.sql.gz" | docker exec -i abase-mysql-prod \
  mysql -u"${DATABASE_USER}" -p"${DATABASE_PASSWORD}" "${DATABASE_NAME}"
```

### 12.8 Restaurar toda a mídia

```bash
docker run --rm \
  -v abase_backend_media:/target \
  -v "${SERVER_DIR}":/source:ro \
  alpine sh -c 'tar -xzf /source/local_media.tar.gz -C /target'

docker run --rm \
  -v abase_backend_media:/source:ro \
  -v /opt/ABASE/data/media:/target \
  alpine sh -c 'cp -a /source/. /target/'
```

### 12.9 Corrigir schema/migrations se necessário

```bash
cd /opt/ABASE/repo
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml up -d backend celery frontend
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml exec -T backend python manage.py migrate
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml exec -T backend python manage.py check
docker exec abase-nginx-prod nginx -s reload
```

### 12.10 Validar anexos e comprovantes

Checklist mínimo:

- saúde em `/api/v1/health/`
- login no web
- abertura de 5 associados com comprovantes
- abertura de 5 contratos com comprovantes de tesouraria
- abertura de 5 anexos de renovação
- importação de arquivo retorno em dry-run
- listagem de contratos e associados carregando normalmente

### 12.11 Limpeza obrigatória da VPS após a importação

```bash
rm -rf "${SERVER_DIR}"
docker builder prune -af --filter until=168h
docker image prune -af --filter until=168h
```

Não remover:

- `/opt/ABASE/data/backups`
- `/opt/ABASE/data/media`
- `/opt/ABASE/env/.env.production`

## 13. Histórico do último deploy validado

### 01/04/2026 — promoção completa local → `abasepiaui.cloud`

- tipo: importação completa de banco + mídia
- servidor: `72.60.58.181`
- domínio: `abasepiaui.cloud`
- branch: `abaseprod`
- commit aplicado no servidor: `8ba0e3f`
- dump importado: `local_db.sql.gz`
- mídia importada: `local_media.tar.gz`
- contagens pós-import: 687 associados, 687 contratos, 2763 parcelas, 726 usuários

Correções que precisaram ser reaplicadas:

- registros faltantes de `django_migrations` para `token_blacklist`
- `ALTER TABLE token_blacklist_outstandingtoken MODIFY jti_hex varchar(255) NOT NULL DEFAULT ''`
- `nginx -s reload` após recreação do frontend

Lições permanentes:

- preservar staging de importação em `/opt/ABASE/import/<release>`, nunca no repositório
- quando o dump vier sem `django_migrations` consistentes, validar `token_blacklist` antes de liberar backend
- sempre validar abertura real de comprovantes e anexos após restore completo

### 03/04/2026 — hotfix operacional na base atual para abril/2026

- tipo: saneamento operacional local antes da promoção para `abasepiaui.cloud`
- escopo: modal de prévia da importação + reversão de abril/2026 para previsão
- comando aplicado:

```bash
docker compose exec -T backend python manage.py revert_discounted_reference_to_forecast --target-ref 2026-04 --dry-run
docker compose exec -T backend python manage.py revert_discounted_reference_to_forecast --target-ref 2026-04 --execute
docker compose exec -T backend python manage.py revert_discounted_reference_to_forecast --target-ref 2026-04 --dry-run
```

- dry-run inicial: `352` casos reparáveis, `0` revisão manual
- execução: `352` casos revertidos, `0` revisão manual
- evidências alteradas na execução:
  - `baixas`: `352`
  - `parcelas`: `352`
  - `rebuilds`: `352`
- dry-run pós-execução: `0` casos remanescentes para `2026-04`
- validação pós-correção na base atual:
  - parcelas de abril em `descontado/liquidada`: `0`
  - `BaixaManual` ativa para abril/2026: `0`
  - parcelas de abril em `em_previsao`: `502`

Relatórios gerados localmente:

- `backend/media/relatorios/legacy_import/revert_discounted_reference_to_forecast_20260403T204435.json`
- `backend/media/relatorios/legacy_import/revert_discounted_reference_to_forecast_20260403T204710.json`
- `backend/media/relatorios/legacy_import/revert_discounted_reference_to_forecast_20260403T204838.json`

Observações permanentes:

- executar sempre `--dry-run` antes de aplicar a reversão em homologação ou produção
- a reversão preserva histórico bruto e neutraliza abril/2026 por cancelamento/soft-delete controlado
- após a execução, validar contratos de amostra na UI para garantir que abril voltou para previsão e não permaneceu contado como pago

### 04/04/2026 — saneamento Mar/Nov + reimportação cronológica Out→Fev

- tipo: saneamento estrutural de ciclos após rebuild incorreto
- escopo:
  - março/2026 pago voltou a contar para ciclo
  - novembro/2025 saiu dos ciclos e ficou quitado fora do ciclo
  - reimportação cronológica dos arquivos retorno de outubro/2025 a fevereiro/2026
- staging usado localmente:
  - host: `backups/legacy_restore_20260401T083933/staged_return_files`
  - dentro do container backend: `/tmp/staged_return_files_20260404`

Arquivos e comandos introduzidos:

- comando novo:

```bash
docker compose exec -T backend python manage.py repair_maristela_cycle_membership --dry-run
docker compose exec -T backend python manage.py repair_maristela_cycle_membership --execute
```

- regra técnica incorporada:
  - `manual_forma_pagamento=conciliacao_maristela_em_ciclo` conta para ciclo
  - `manual_forma_pagamento=conciliacao_maristela_fora_ciclo` fica quitado fora do ciclo

Execução local realizada:

```bash
docker compose exec -T backend \
  python manage.py repair_maristela_cycle_membership --dry-run \
  --report-json /app/backend/media/relatorios/legacy_import/repair_maristela_cycle_membership_dry_run_20260404.json

docker compose exec -T backend \
  python manage.py repair_maristela_cycle_membership --execute \
  --report-json /app/backend/media/relatorios/legacy_import/repair_maristela_cycle_membership_execute_pass1_20260404.json

docker compose exec -T backend mkdir -p /tmp/staged_return_files_20260404
docker cp backups/legacy_restore_20260401T083933/staged_return_files/. \
  <backend_container_id>:/tmp/staged_return_files_20260404/

docker compose exec -T backend \
  python manage.py reimport_staged_return_files --dry-run \
  --staging-dir /tmp/staged_return_files_20260404 \
  --report-json /app/backend/media/relatorios/legacy_import/reimport_staged_return_files_dry_run_20260404.json

docker compose exec -T backend \
  python manage.py reimport_staged_return_files --execute \
  --staging-dir /tmp/staged_return_files_20260404 \
  --report-json /app/backend/media/relatorios/legacy_import/reimport_staged_return_files_execute_20260404.json

docker compose exec -T backend \
  python manage.py repair_maristela_cycle_membership --execute \
  --report-json /app/backend/media/relatorios/legacy_import/repair_maristela_cycle_membership_execute_pass2_20260404.json

docker compose exec -T backend \
  python manage.py repair_maristela_cycle_membership --dry-run \
  --report-json /app/backend/media/relatorios/legacy_import/repair_maristela_cycle_membership_final_dry_run_20260404.json

docker compose exec -T backend rm -rf /tmp/staged_return_files_20260404
```

Resultados locais da auditoria e da execução:

- dry-run inicial:
  - `associados_auditados`: `530`
  - `repairable`: `432`
  - `manual_review`: `29`
- execução pass 1:
  - `repaired`: `432`
  - `manual_review`: `29`
- reimportação cronológica concluída:
  - `2025-10-01`
  - `2025-11-01`
  - `2025-12-01`
  - `2026-01-01`
  - `2026-02-01`
- execução pass 2:
  - `repaired`: `9`
  - `manual_review`: `20`
- dry-run final:
  - `repairable`: `0`
  - `manual_review`: `20`

Métricas finais observadas na base local:

- `march_in_cycle`: `450`
- `march_outside`: `21`
- `nov_in_cycle`: `4`
- `nov_outside`: `253`
- `associados_ativos`: `239`
- `associados_inadimplentes`: `332`
- `associados_inativos`: `10`

Leitura correta dessas métricas:

- a fila automática foi zerada (`repairable=0`)
- os resíduos `march_outside=21` e `nov_in_cycle=4` pertencem aos `20` casos classificados como `manual_review`
- homologação/produção só devem seguir com revisão amostral desses `20` casos e aceite explícito do saldo manual

Relatórios gerados localmente:

- `/app/backend/media/relatorios/legacy_import/repair_maristela_cycle_membership_dry_run_20260404.json`
- `/app/backend/media/relatorios/legacy_import/repair_maristela_cycle_membership_execute_pass1_20260404.json`
- `/app/backend/media/relatorios/legacy_import/reimport_staged_return_files_dry_run_20260404.json`
- `/app/backend/media/relatorios/legacy_import/reimport_staged_return_files_execute_20260404.json`
- `/app/backend/media/relatorios/legacy_import/repair_maristela_cycle_membership_execute_pass2_20260404.json`
- `/app/backend/media/relatorios/legacy_import/repair_maristela_cycle_membership_final_dry_run_20260404.json`

Exemplos do saldo `manual_review` que exigem decisão manual:

- `71339477300` JEAN DOUGLAS RODRIGUES REIS
  - março continuou aparecendo como movimento financeiro fora do ciclo
- `05855647366` RAIMUNDO NONATO MOREIRA FILHO
  - valores conflitantes para a mesma competência: `191.17` e `200.00`
- `32784066304` FRANCISCO JORGE DA SILVA
  - valores conflitantes para a mesma competência: `275.00`, `275.46` e `300.00`
- `41233875353` MARIA DE LOURDES PEREIRA DOS SANTOS
  - valores conflitantes para a mesma competência: `150.00` e `200.00`

Lições permanentes:

- março/2026 e novembro/2025 não podem compartilhar a mesma semântica de pagamento manual
- o staging de retorno deve ser copiado para dentro do container em `/tmp/` quando o compose não monta `backups/`
- o diretório temporário `/tmp/staged_return_files_*` deve ser removido ao fim da operação
- a promoção para servidor deve repetir a mesma ordem: repair pass 1 → reimportação Out→Fev → repair pass 2 → dry-run final

### 04/04/2026 — hardening do importador de arquivo retorno

- tipo: correção de estabilidade operacional em produção
- incidente observado:
  - a prévia do arquivo retorno abria corretamente
  - após confirmar, a UI entrava em polling
  - a rota `GET /api/v1/importacao/arquivo-retorno/` podia saturar o backend e responder `502 Bad Gateway`
  - quando o Celery ficava indisponível, a importação podia permanecer presa em `pendente/processando`

Correções aplicadas no código:

- a listagem de `ArquivoRetorno` deixou de recalcular o resumo financeiro pesado no polling do histórico
- a listagem de `ArquivoRetorno` agora devolve `resumo={}` e `financeiro=null` no histórico, porque a UI não consome esses blocos nessa rota
- o resumo financeiro passou a ser cacheado em `resultado_resumo["financeiro"]` ao final do processamento
- a tela de importação passou a buscar o financeiro detalhado em endpoint dedicado, sob demanda
- o histórico deixou de fazer polling agressivo
- a confirmação agora faz fallback inline quando nenhum worker Celery responde ao ping
- a rota `GET /api/v1/importacao/duplicidades-financeiras/` deixou de materializar toda a base em memória antes de paginar
- o badge lateral de duplicidades passou a usar `summary_only=1`, retornando apenas `count` + `kpis`, sem serializar linhas desnecessárias
- `resolver-devolucao` e `descartar` deixaram de refazer a listagem inteira de duplicidades só para retornar a linha atualizada

Efeito esperado:

- queda forte de carga no backend durante a importação
- redução de `502` na tela `/importacao`
- redução de `500` no badge lateral de duplicidades e na sidebar da tesouraria
- fim do estado “pendente infinito” quando o worker estiver fora do ar

### 04/04/2026 — validação final local do pacote importação + análise

- tipo: validação pré-release local
- branch: `abaseprod`
- base local validada na árvore de trabalho desta janela
- escopo validado em verde:
  - importação de retorno com dry-run, cancelamento por `X` e confirmação explícita
  - autoimportação de associados com status `importado`
  - dashboard `/analise` para `COORDENADOR`, `ANALISTA` e `ADMIN`
  - exclusão lógica elegível da esteira e bloqueio de visibilidade entre analistas
  - regeneração do schema OpenAPI e artefatos Kubb
- comandos que fecharam em verde:

```bash
docker compose run --rm backend-tools \
  python manage.py test \
  apps.importacao.tests.test_reconciliacao \
  apps.importacao.tests.test_services \
  apps.importacao.tests.test_reimport_staged_return_files \
  apps.esteira.tests.test_analise

docker compose run --rm frontend sh -lc \
  "pnpm --filter @abase/web test -- --runInBand --runTestsByPath \
  src/app/'(dashboard)'/importacao/page.test.tsx \
  src/lib/navigation.test.ts"

docker compose run --rm frontend sh -lc \
  "pnpm --filter @abase/web type-check"
```

- comando bloqueador que permaneceu vermelho:

```bash
docker compose run --rm backend-tools \
  python manage.py test \
  apps.accounts apps.associados apps.contratos apps.esteira \
  apps.financeiro apps.importacao apps.refinanciamento apps.relatorios apps.tesouraria
```

- resultado consolidado da suíte completa: `323` testes, `17` falhas e `6` erros
- áreas ainda quebradas fora do pacote desta release:
  - `accounts`: gestão de usuários internos e importações legadas
  - `associados`: agenda/materialização de contrato e compatibilidade mobile legado
  - `contratos`: duplicate billing, renovação e reparo de referência deslocada
  - `refinanciamento`: reaproveitamento de refinanciamento após devolução
  - `tesouraria`: pagamentos do agente, materialização de ciclos, resultado mensal, devoluções e fluxo completo com `termo_antecipacao`
- correção incorporada nesta revisão:
  - o comando `reimport_staged_return_files` agora confirma automaticamente arquivos que entram em `aguardando_confirmacao`, para operar corretamente com o novo fluxo de importação
- decisão operacional:
  - deploy oficial bloqueado até a suíte completa do backend fechar em verde ou haver aceite explícito do risco

### 04/04/2026 — fechamento da suíte completa do backend (7 blockers)

- tipo: correção de testes e lógica de negócio — sem deploy no servidor
- branch: `abaseprod`
- escopo: todos os 7 blockers listados em `docs/NEXT_SESSION_API_SUITE_BLOCKERS.md` foram corrigidos

Blockers corrigidos:

| # | Área | Descrição |
|---|------|-----------|
| 1 | `accounts` | `LegacyDatabaseSyncAuthTestCase.setUpTestData` criava tabelas raw (`users`, `roles`, `role_user`) que persistiam com `--keepdb`; adicionado `DROP TABLE IF EXISTS` no início de `setUpTestData` e em `tearDownClass` |
| 2 | `refinanciamento` | Mensagem de erro em `strategies.py` divergia do teste: "renovação em andamento" → "refinanciamento ativo" |
| 3 | `refinanciamento` | Fluxo legado sem `termo_antecipacao`: `aprovar()` bloqueava em `EM_ANALISE_RENOVACAO`; adicionado branch que detecta o caso sem-termo, materializa o próximo ciclo via `rebuild_contract_cycle_state` e define status `CONCLUIDO` + `ciclo_destino` diretamente |
| 4 | `refinanciamento` | Asserção de teste stale em `test_refinanciamento_pagamentos.py:564`; após `devolver_para_analise`, `coordenador_note = "Revisar assinatura do termo."` é preservado corretamente — o expected foi corrigido |
| 5 | `contratos` | `Contrato.save()` sobrescrevia `comissao_agente` explicitamente definido; auto-cálculo agora só dispara quando o campo está em zero |
| 6 | `contratos` | `_build_eligible_references` em `cycle_projection.py` blacklistava meses de origem de refis EFETIVADO legado porque o `PagamentoMensalidade` associado tinha `status_code ≠ 1/4`; adicionado `legado_refi_covered_refs` para excluir esses meses do `blocked_references` |
| 7 | `contratos` | `cycle_rebuild.py` rematerializava parcelas de meses cobertos por `BaixaManual`; adicionada consulta de `baixa_manual_refs` e skip (com soft-delete do existente) antes do loop de parcelas |

Arquivos alterados:

- `backend/apps/accounts/tests/test_legacy_passwords.py`
- `backend/apps/refinanciamento/strategies.py`
- `backend/apps/refinanciamento/services.py`
- `backend/apps/refinanciamento/tests/test_refinanciamento_pagamentos.py`
- `backend/apps/contratos/models.py`
- `backend/apps/contratos/cycle_projection.py`
- `backend/apps/contratos/cycle_rebuild.py`

Situação pós-correção:

- suíte completa do backend esperada em verde
- gate técnico da seção `10.1` liberado para rodar e validar antes do próximo deploy

## 14. Próximo deploy planejado em `abasepiaui.com`

Objetivo do próximo deploy:

- promover o código atual do branch `abaseprod`
- atualizar a produção com backup preventivo completo
- executar o protocolo Mar/Nov + reimportação Out→Fev no servidor oficial
- validar o saldo residual de `20` casos `manual_review`

Pré-condições:

- rerodar o gate técnico da seção `10.1`
- registrar o commit alvo com `git rev-parse HEAD`
- preparar artefatos fora do repositório:
  - dump SQL da origem escolhida
  - pacote de `media/`
  - staging `backups/legacy_restore_20260401T083933/staged_return_files`

### 14.1 Backup preventivo antes da atualização

Na VPS `.com`:

```bash
cd /opt/ABASE/repo
bash deploy/hostinger/scripts/backup_now.sh
```

Além do backup padrão, preservar:

- dump atual da produção
- cópia de `/opt/ABASE/data/media`
- cópia do staging usado para a reimportação em `/opt/ABASE/import/<release>/staged_return_files`

### 14.2 Deploy de código sem lixo extra na VPS

```bash
cd /opt/ABASE/repo
git fetch origin
git checkout abaseprod
git pull --ff-only origin abaseprod

docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml build backend frontend celery

docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml up -d backend frontend celery

docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml exec -T backend python manage.py migrate

docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml exec -T backend python manage.py check

docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml exec -T celery celery -A config inspect ping
```

Regra de limpeza:

- não copiar dump, `media.tar.gz` ou relatórios para dentro de `/opt/ABASE/repo`
- usar apenas `/opt/ABASE/import/<release>` para staging externo

### 14.3 Protocolo de produção Mar/Nov + reimportação Out→Fev

1. Dry-run do saneamento:

```bash
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml exec -T backend \
  python manage.py repair_maristela_cycle_membership --dry-run \
  --report-json /app/backend/media/relatorios/legacy_import/repair_maristela_cycle_membership_dry_run_server.json
```

2. Execução do pass 1:

```bash
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml exec -T backend \
  python manage.py repair_maristela_cycle_membership --execute \
  --report-json /app/backend/media/relatorios/legacy_import/repair_maristela_cycle_membership_execute_pass1_server.json
```

3. Copiar o staging de retorno para dentro do container backend:

```bash
BACKEND_CID=$(docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml ps -q backend)

docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml exec -T backend \
  mkdir -p /tmp/staged_return_files_server

docker cp /opt/ABASE/import/<release>/staged_return_files/. \
  "${BACKEND_CID}:/tmp/staged_return_files_server/"
```

4. Dry-run da reimportação cronológica:

```bash
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml exec -T backend \
  python manage.py reimport_staged_return_files --dry-run \
  --staging-dir /tmp/staged_return_files_server \
  --report-json /app/backend/media/relatorios/legacy_import/reimport_staged_return_files_dry_run_server.json
```

5. Execução da reimportação cronológica:

```bash
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml exec -T backend \
  python manage.py reimport_staged_return_files --execute \
  --staging-dir /tmp/staged_return_files_server \
  --report-json /app/backend/media/relatorios/legacy_import/reimport_staged_return_files_execute_server.json
```

6. Execução do pass 2:

```bash
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml exec -T backend \
  python manage.py repair_maristela_cycle_membership --execute \
  --report-json /app/backend/media/relatorios/legacy_import/repair_maristela_cycle_membership_execute_pass2_server.json
```

7. Dry-run final obrigatório:

```bash
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml exec -T backend \
  python manage.py repair_maristela_cycle_membership --dry-run \
  --report-json /app/backend/media/relatorios/legacy_import/repair_maristela_cycle_membership_final_dry_run_server.json
```

8. Limpeza do staging temporário dentro do container:

```bash
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml exec -T backend \
  rm -rf /tmp/staged_return_files_server
```

### 14.4 Checklist pós-execução em `.com`

Validar no relatório final e por amostra na UI:

- março dentro do ciclo correspondente
- novembro fora do ciclo
- nenhum ciclo 1 contendo novembro/2025
- nenhum ciclo 1 com parcela “em previsão” incoerente herdada do rebuild anterior
- associados `ativo` e `inadimplente` coerentes após o recálculo
- `celery -A config inspect ping` respondendo antes de qualquer importação
- login, anexos, comprovantes e importação dry-run funcionando

Aceite do saldo residual:

- o protocolo automático deve terminar com `repairable=0`
- se permanecer saldo `manual_review`, registrar quantidade, CPFs afetados e o arquivo de relatório
- a promoção para produção só deve ocorrer com aceite explícito desse saldo manual

### 14.5 Rollback específico desta operação

Se o saneamento ou a reimportação no servidor produzir resultado inválido:

1. parar `backend`, `frontend` e `celery`
2. restaurar o dump preventivo da produção
3. restaurar `/opt/ABASE/data/media`
4. subir novamente a stack
5. recarregar o Nginx

Comandos-base:

```bash
cd /opt/ABASE/repo
bash deploy/hostinger/scripts/restore_db.sh /opt/ABASE/data/backups/<dump.sql.gz>
bash deploy/hostinger/scripts/restore_files.sh /opt/ABASE/data/backups/<media.tar.gz>
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml up -d
docker exec abase-nginx-prod nginx -s reload
```

## 15. Ajuste do app mobile após entrada da produção oficial

Arquivos do app novo:

- `abase_mobile_new/.env`
- `abase_mobile_new/eas.json`
- `abase_mobile_new/src/services/api/constants.ts`

Valor final:

```env
EXPO_PUBLIC_API_BASE_URL=https://abasepiaui.com/api/v1
```

Se o app legado ainda existir:

- revisar `abase_mobile/Abase_mobile_legado/abasev2app/.env`
- apontar `API_URL` e correlatos para `https://abasepiaui.com/api`

Regra:

- não deixar fallback antigo em `.cloud` no build de produção do app

## 16. Build iOS via Expo EAS

Pré-requisitos:

- conta Expo autenticada
- conta Apple Developer ativa
- App Store Connect configurado para o bundle final

Comandos:

```bash
cd /mnt/d/apps/abasev2/abasev2/abase_mobile_new
npm ci
npx expo install --check
eas login
eas whoami
npm run eas:build:ios:preview
npm run eas:build:ios:production
npm run eas:submit:ios:production
```

Fluxo recomendado:

- primeiro gerar `preview`
- validar login, upload e abertura de anexos
- só então gerar `production`

## 17. Rollback

Se o deploy de código falhar:

```bash
cd /opt/ABASE/repo
bash deploy/hostinger/scripts/rollback.sh
```

Se o problema for banco ou mídia:

- restore do banco com `restore_db.sh`
- restore da mídia com `restore_files.sh`
- `docker compose up -d`
- `docker exec abase-nginx-prod nginx -s reload`

## 18. Encerramento da operação

Uma operação só termina quando estes itens estão fechados:

- `docker compose ps` sem container crítico em `unhealthy`
- `/api/v1/health/` respondendo `200`
- login web funcionando
- pelo menos 3 anexos e 3 comprovantes abrindo de ponta a ponta
- backup preventivo identificado pelo timestamp da janela
- staging temporário removido da VPS
- logs da operação salvos em `/opt/ABASE/logs`

## 19. Regra de manutenção deste documento

Sempre que houver mudança real de protocolo:

- atualizar apenas este arquivo
- não recriar runbooks paralelos em `deploy/`
- preservar o histórico antigo no Git, não em novos `.md` soltos
