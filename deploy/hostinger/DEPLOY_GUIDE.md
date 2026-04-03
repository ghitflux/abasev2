# Runbook Único de Setup, Hardening, Backup, Restore e Deploy

> Arquivo autoritativo para `abasepiaui.com` (produção) e `abasepiaui.cloud` (homologação/teste).
> Este documento substitui os demais `.md` removidos de `deploy/`.

## 1. Escopo e regra operacional

Este runbook cobre:

- setup inicial da VPS de produção
- hardening do host e protocolo mínimo anti-invasão
- deploy incremental de código
- restore completo de banco + mídia
- promoção completa de base para homologação
- histórico do último deploy validado
- plano do próximo deploy em `abasepiaui.cloud`
- ajuste do app mobile para a API final em `abasepiaui.com`
- preparo do build iOS via Expo EAS

Regras fixas:

- produção oficial: `https://abasepiaui.com`
- homologação/teste: `https://abasepiaui.cloud`
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

### Homologação

- domínio: `abasepiaui.cloud`
- uso: ensaio de deploy, restore completo, validação de anexos, testes de reconciliação e importações
- política: recebe backup e importação completa antes de releases maiores

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
- imagens Docker: atualizar primeiro em `abasepiaui.cloud`, validar e só então promover para produção
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

## 7. Ajustes de domínio antes do primeiro deploy de produção

Arquivos que precisam refletir o domínio final:

- `deploy/hostinger/nginx/nginx.conf`
- `deploy/hostinger/docker-compose.prod.yml`
- `deploy/hostinger/.env.production.example`

Trocas mínimas para produção:

- `abasepiaui.cloud` → `abasepiaui.com`
- `www.abasepiaui.cloud` → `www.abasepiaui.com`
- `https://abasepiaui.cloud/api/v1` → `https://abasepiaui.com/api/v1`

Homologação continua com `.cloud`.

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

## 12. Protocolo de promoção completa para homologação `abasepiaui.cloud`

Use este fluxo quando a homologação precisar receber uma base completa com todos os anexos e comprovantes.

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

## 14. Próximo deploy planejado em `abasepiaui.cloud`

Objetivo:

- backup completo do estado atual da homologação
- importação completa da fonte de verdade mais recente
- promoção do código atual do branch `abaseprod`
- validação de anexos, comprovantes e fluxo de importação de retorno

Fila mínima já pronta para homologação após o último deploy histórico:

- login/auth revisado com sessão de 48h e recuperação manual para agente
- redistribuição obrigatória de carteira ao remover/desativar agente
- dry-run com confirmação antes da importação do arquivo retorno
- saneamento operacional de comprovantes/anexos legados
- ajuste da listagem de contratos para exibir valor disponível

Checklist operacional do próximo deploy em `.cloud`:

1. `git rev-parse HEAD` local e registrar commit alvo.
2. Gerar dump completo e `media.tar.gz` da origem escolhida.
3. Copiar artefatos para `/opt/ABASE/import/release_<timestamp>`.
4. Rodar `backup_now.sh` na homologação.
5. Parar `frontend`, `backend` e `celery`.
6. Importar banco.
7. Restaurar mídia completa.
8. Rodar `git pull origin abaseprod`.
9. Rebuildar `backend`, `frontend` e `celery`.
10. Subir stack e rodar `migrate` + `check`.
11. Validar login, anexos, comprovantes, contratos, importação dry-run e redistribuição de agente.
12. Remover staging e fazer prune controlado.

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
