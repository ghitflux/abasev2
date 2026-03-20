# ABASE v2 — Guia de Deploy Completo (VPS Hostinger)

> **Validado no deploy real em `72.60.58.181` — 17/03/2026**
> Domínio: `abasepiaui.cloud` | Branch: `abaseprod`
> Repositório: `https://github.com/ghitflux/abasenewv2.git`

---

## ARQUITETURA DE PRODUÇÃO

```text
Internet
  └── Nginx :80/:443
        ├── /api/auth/      → frontend:3000  (Next.js Route Handlers — auth)
        ├── /api/backend/   → frontend:3000  (Next.js proxy com Bearer token)
        ├── /api/media/     → /app/media/    (servido direto pelo nginx)
        ├── /api/           → backend:8000   (Django REST API)
        ├── /media/         → /app/media/
        ├── /static/        → /app/staticfiles/
        └── /               → frontend:3000  (Next.js)

frontend:3000 (Next.js standalone)
  /api/auth/login   → POST http://backend:8000/api/v1/auth/login/  (gera cookie JWT)
  /api/backend/...  → http://backend:8000/api/v1/... (injeta Bearer do cookie)
  /api/media/...    → nginx serve direto (Django não serve /media/ com DEBUG=False)

backend:8000 (Gunicorn, 4 workers)
  └── MySQL:3306 / Redis:6379 (internos, sem exposição ao host)

celery (worker, concurrency=2)
  └── Redis:6379 (broker + resultado)
```

### ⚠️ Regra crítica do nginx

O Next.js possui **3 prefixos de Route Handlers** que devem ir para `frontend:3000`,
NÃO para o Django. Eles devem aparecer **antes** do bloco genérico `location /api/`:

|Prefixo|Destino|Motivo|
|---|---|---|
|`/api/auth/`|`frontend:3000`|Login/logout/me — gerencia cookies httpOnly|
|`/api/backend/`|`frontend:3000`|Proxy reverso — injeta Bearer token do cookie|
|`/api/media/`|filesystem `/app/media/`|Django não serve `/media/` com `DEBUG=False`|
|`/api/`|`backend:8000`|Django REST API|

---

## FASE 1 — PRÉ-REQUISITOS NO CÓDIGO

### 1.1 Next.js — output standalone

```typescript
// apps/web/next.config.ts
const nextConfig: NextConfig = {
  output: process.env.NODE_ENV === "production" ? "standalone" : undefined,
  // ...
};
```

### 1.2 Health check no Django

```python
# backend/config/urls.py
from django.http import JsonResponse

def health_check(request):
    return JsonResponse({"status": "ok", "service": "abase-backend"})

urlpatterns = [
    path("api/v1/health/", health_check, name="health-check"),
    # ...
]
```

### 1.3 Branch de produção

```bash
git checkout -b abaseprod
git push abasenewv2 abaseprod
```

---

## FASE 2 — BOOTSTRAP DA VPS

```bash
ssh root@<IP_VPS>

apt update && apt upgrade -y
timedatectl set-timezone America/Fortaleza
apt install -y curl git ufw fail2ban ca-certificates gnupg lsb-release \
    unzip apt-transport-https software-properties-common netcat-openbsd
```

### 2.1 Usuário deploy

```bash
adduser deploy
usermod -aG sudo deploy
mkdir -p /home/deploy/.ssh
cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh && chmod 600 /home/deploy/.ssh/authorized_keys
```

### 2.2 Docker

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

### 2.3 Firewall

```bash
ufw default deny incoming && ufw default allow outgoing
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp
ufw enable
```

### 2.4 Diretórios e permissões

```bash
mkdir -p /opt/ABASE/repo
mkdir -p /opt/ABASE/env
mkdir -p /opt/ABASE/data/{db,redis,media,static,backups/{daily,weekly,monthly},certbot/{conf,www}}
mkdir -p /opt/ABASE/logs
chown -R deploy:deploy /opt/ABASE

# OBRIGATÓRIO: sem isso o collectstatic falha com "Permission denied"
chmod 777 /opt/ABASE/data/static
chmod 777 /opt/ABASE/data/media
```

---

## FASE 3 — CLONAR E CONFIGURAR

```bash
cd /opt/ABASE
git clone -b abaseprod https://github.com/ghitflux/abasenewv2.git repo
```

### 3.1 Arquivo de ambiente

```bash
cp /opt/ABASE/repo/deploy/hostinger/.env.production.example /opt/ABASE/env/.env.production
chmod 600 /opt/ABASE/env/.env.production
nano /opt/ABASE/env/.env.production
```

Variáveis obrigatórias:

```env
# Django
DJANGO_SETTINGS_MODULE=config.settings.production
SECRET_KEY=<python3 -c "import secrets; print(secrets.token_urlsafe(64))">
DEBUG=False
ALLOWED_HOSTS=abasepiaui.cloud,www.abasepiaui.cloud
CSRF_TRUSTED_ORIGINS=https://abasepiaui.cloud,https://www.abasepiaui.cloud
CORS_ALLOWED_ORIGINS=https://abasepiaui.cloud

# Banco
DATABASE_NAME=abase_v2
DATABASE_USER=abase
DATABASE_PASSWORD=<senha forte>
DATABASE_HOST=mysql
DATABASE_PORT=3306

# MySQL container
MYSQL_ROOT_PASSWORD=<senha forte>
MYSQL_DATABASE=abase_v2
MYSQL_USER=abase
MYSQL_PASSWORD=<igual a DATABASE_PASSWORD>

# Redis / Celery
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# Frontend
NEXT_PUBLIC_API_URL=https://abasepiaui.cloud/api/v1
INTERNAL_API_URL=http://backend:8000/api/v1
```

---

## FASE 4 — SSL

### 4.1 Verificar DNS primeiro

```bash
dig +short abasepiaui.cloud
# Deve retornar o IP da VPS. Se não, aguardar propagação antes do Certbot.
```

### 4.2 Certificado temporário (quando DNS ainda não propagou)

```bash
mkdir -p /opt/ABASE/data/certbot/conf/live/abasepiaui.cloud
openssl req -x509 -nodes -newkey rsa:4096 -days 365 \
  -keyout /opt/ABASE/data/certbot/conf/live/abasepiaui.cloud/privkey.pem \
  -out /opt/ABASE/data/certbot/conf/live/abasepiaui.cloud/fullchain.pem \
  -subj "/CN=abasepiaui.cloud"
cp /opt/ABASE/data/certbot/conf/live/abasepiaui.cloud/fullchain.pem \
   /opt/ABASE/data/certbot/conf/live/abasepiaui.cloud/chain.pem
```

### 4.3 Certificado real Let's Encrypt (após DNS propagar)

O nginx já está configurado com `location /.well-known/acme-challenge/` apontando para
`/var/www/certbot`. Use o método **webroot** — não é necessário derrubar o nginx:

```bash
# NÃO precisa parar o nginx — usa webroot via nginx ativo
docker run --rm \
  -v /opt/ABASE/data/certbot/conf:/etc/letsencrypt \
  -v /opt/ABASE/data/certbot/www:/var/www/certbot \
  certbot/certbot certonly --webroot \
  --webroot-path=/var/www/certbot \
  --email ghitflux@gmail.com --agree-tos --no-eff-email \
  -d abasepiaui.cloud -d www.abasepiaui.cloud
```

O certbot salva em `live/abasepiaui.cloud-0001/` se já existia um cert anterior.
Corrija com symlink **relativo** (caminho absoluto não funciona dentro do container):

```bash
# Se o cert foi salvo em abasepiaui.cloud-0001 (versão nova):
# 1. Mover/renomear o diretório antigo (autoassinado)
mv /opt/ABASE/data/certbot/conf/live/abasepiaui.cloud \
   /opt/ABASE/data/certbot/conf/live/abasepiaui.cloud.selfsigned.bak

# 2. Criar symlink RELATIVO (obrigatório — caminho absoluto quebra dentro do container)
cd /opt/ABASE/data/certbot/conf/live
ln -s abasepiaui.cloud-0001 abasepiaui.cloud

# 3. Restart nginx para carregar o novo cert
docker compose -f /opt/ABASE/repo/deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production restart nginx

# 4. Verificar issuer (deve ser "Let's Encrypt", não autoassinado)
echo | openssl s_client -connect localhost:443 -servername abasepiaui.cloud 2>/dev/null \
  | openssl x509 -noout -issuer -dates
```

> ⚠️ **ERRO COMUM:** Criar symlink com `ln -s /opt/ABASE/data/certbot/conf/live/abasepiaui.cloud-0001 abasepiaui.cloud`
> (caminho absoluto do host) faz o link ficar quebrado DENTRO do container nginx,
> que monta o volume em `/etc/letsencrypt/`. Use sempre `ln -s abasepiaui.cloud-0001 abasepiaui.cloud`
> (caminho relativo).

### 4.4 Renovação automática (cron)

```bash
echo "0 0,12 * * * root docker run --rm \
  -v /opt/ABASE/data/certbot/conf:/etc/letsencrypt \
  -v /opt/ABASE/data/certbot/www:/var/www/certbot \
  certbot/certbot renew --quiet && \
  docker exec abase-nginx-prod nginx -s reload" \
  | tee /etc/cron.d/certbot-renew
```

---

## FASE 5 — DEPLOY

```bash
cd /opt/ABASE/repo
docker compose -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  up -d --build
```

Aguardar todos os containers ficarem `healthy` (~2 min):

```bash
watch -n5 'docker ps --format "table {{.Names}}\t{{.Status}}"'
```

Verificar que migrations e collectstatic rodaram:

```bash
docker logs abase-backend-prod --tail=30
# Deve conter: "Applying migrations..." e "X static files copied"
```

---

## FASE 6 — IMPORTAR BANCO DE DADOS

### 6.1 Exportar do Docker local (máquina dev)

```bash
docker exec abase-v2-mysql-1 mysqldump \
  -uroot -p<SENHA_ROOT_LOCAL> \
  --single-transaction --routines --triggers \
  abase_v2 > /tmp/abase_dump.sql
gzip /tmp/abase_dump.sql
```

### 6.2 Enviar para VPS e importar

```bash
# Enviar
scp /tmp/abase_dump.sql.gz root@<IP_VPS>:/opt/ABASE/data/backups/

# Na VPS — importar
gunzip -c /opt/ABASE/data/backups/abase_dump.sql.gz | \
  docker exec -i abase-mysql-prod \
  mysql -uroot -p<MYSQL_ROOT_PASSWORD> abase_v2
```

### 6.3 Confirmar dados

```bash
docker exec abase-mysql-prod mysql -uabase -p<MYSQL_PASSWORD> abase_v2 -e "
  SELECT 'associados' t, COUNT(*) n FROM associados_associado
  UNION ALL SELECT 'contratos', COUNT(*) FROM contratos_contrato
  UNION ALL SELECT 'accounts_user', COUNT(*) FROM accounts_user
  UNION ALL SELECT 'legacy_users', COUNT(*) FROM users;
" 2>/dev/null
```

### 6.4 Autenticação com senhas legado (bcrypt Laravel)

O sistema usa `LegacyLaravelUserBackend` + `LegacyLaravelBcryptPasswordHasher`
para autenticar usuários cujas senhas estão na tabela `users` como hashes `$2y$`
(bcrypt do Laravel/Sanctum) — **sem necessidade de reset de senha**.

Isso funciona automaticamente desde que a tabela `users` esteja no banco.
Verificar:

```bash
docker exec abase-mysql-prod mysql -uabase -p<MYSQL_PASSWORD> abase_v2 \
  -e "SELECT COUNT(*) FROM users WHERE password LIKE '\$2y\$%';" 2>/dev/null
# Deve retornar > 0
```

---

## FASE 7 — IMPORTAR ARQUIVOS DE MÍDIA

Use streaming direto Docker → VPS para evitar arquivos intermediários grandes.
Salve o script abaixo como `upload_media.py` e execute localmente:

```python
# upload_media.py — executar na máquina de desenvolvimento
import subprocess, paramiko, time

VPS_IP   = "<IP_VPS>"
VPS_USER = "root"
VPS_PASS = "<SENHA_VPS>"
# Nome do volume Docker local com os arquivos de mídia:
VOLUME   = "abase-v2_backend_media"
# Pastas dentro do volume a enviar:
PASTAS   = ["documentos", "esteira", "pagamentos_mensalidades",
            "refinanciamentos", "arquivos_retorno", "relatorios"]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_IP, username=VPS_USER, password=VPS_PASS, timeout=60)

channel = ssh.get_transport().open_session()
channel.exec_command("tar -xzC /opt/ABASE/data/media/")

proc = subprocess.Popen(
    ["docker", "run", "--rm", "-v", f"{VOLUME}:/m", "alpine",
     "tar", "-czC", "/m"] + PASTAS,
    stdout=subprocess.PIPE
)

sent, start, ultimo = 0, time.time(), 0
while chunk := proc.stdout.read(131072):
    channel.sendall(chunk)
    sent += len(chunk)
    if sent - ultimo >= 50 * 1024 * 1024:
        print(f"  {sent/1024/1024:.0f}MB em {time.time()-start:.0f}s")
        ultimo = sent

channel.shutdown_write()
proc.wait()
print(f"Concluído: {sent/1024/1024:.1f}MB, exit={channel.recv_exit_status()}")
ssh.close()
```

```bash
pip install paramiko
python upload_media.py
```

### Verificar após upload

```bash
# Na VPS
find /opt/ABASE/data/media -type f | wc -l
du -sh /opt/ABASE/data/media/

# Testar acesso
curl -o /dev/null -sw '%{http_code}\n' \
  https://<DOMINIO>/api/media/documentos/associados/<CPF>/documento_frente/<arquivo>.jpeg
# Esperado: 200
```

---

## FASE 8 — VALIDAÇÃO COMPLETA

```bash
# 1. Todos os containers healthy?
docker ps --format 'table {{.Names}}\t{{.Status}}'

# 2. API Django respondendo?
curl -s https://<DOMINIO>/api/v1/health/
# → {"status": "ok", "service": "abase-backend"}

# 3. Rota auth vai para Next.js? (deve ser 400, não 404)
curl -sw '\nHTTP:%{http_code}\n' -X POST https://<DOMINIO>/api/auth/login \
  -H 'Content-Type: application/json' -d '{"email":"x","password":"x"}'

# 4. Proxy backend via Next.js? (deve ser 401, não 404)
curl -sw '\nHTTP:%{http_code}\n' -H 'Authorization: Bearer invalid' \
  https://<DOMINIO>/api/backend/associados

# 5. Mídia acessível?
curl -o /dev/null -sw 'HTTP:%{http_code}\n' \
  https://<DOMINIO>/api/media/refinanciamentos/agente.pdf

# 6. Login real funciona?
curl -s -X POST https://<DOMINIO>/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@abase.com","password":"<SENHA>"}'
# → {"user": {"id": ..., "primary_role": "ADMIN", ...}}
```

---

## ATUALIZAÇÃO CONTÍNUA (DEPLOYS SUBSEQUENTES)

```bash
cd /opt/ABASE/repo
git pull origin abaseprod

# Rebuild dos serviços alterados
docker compose -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  up -d --build --no-deps backend frontend

# Se nginx.conf foi alterado — RESTART obrigatório (não apenas reload)
# git pull cria novo inode; o container mantém o inode antigo até ser recriado
docker compose -f deploy/hostinger/docker-compose.prod.yml restart nginx
```

---

## ERROS CONHECIDOS E SOLUÇÕES

|Sintoma|Causa raiz|Solução|
|---|---|---|
|`collectstatic: Permission denied`|Bind mount sem permissão de escrita|`chmod 777 /opt/ABASE/data/static /opt/ABASE/data/media`|
|`/api/auth/login` → 404|nginx envia para Django (rota não existe lá)|Adicionar `location /api/auth/` antes de `location /api/` no nginx|
|`/api/backend/...` → 404|nginx envia para Django|Adicionar `location /api/backend/` antes de `location /api/`|
|`/api/media/...` → 404|Django não serve `/media/` com `DEBUG=False`|nginx serve `/api/media/` com `alias /app/media/`|
|`nginx -s reload` não aplica config nova|`git pull` troca inode; container usa o antigo|`docker compose restart nginx`|
|Login → "Credenciais inválidas"|Tabela `users` (hashes bcrypt) não importada|Incluir `users`, `roles`, `role_user` no dump|
|Dashboard vazio após login|`/api/backend/` retornando 404|Corrigir nginx (ver acima)|
|`createsuperuser` falha com `--username`|`USERNAME_FIELD = "email"`|Usar flag `--email`|
|Certbot falha|DNS não aponta para o IP da VPS|Usar certificado autoassinado até DNS propagar|
|SSL still autoassinado após certbot|Symlink absoluto quebra dentro do container nginx|Usar symlink relativo: `ln -s abasepiaui.cloud-0001 abasepiaui.cloud`|
|`live/abasepiaui.cloud-0001` gerado|Cert anterior já existia no diretório|Mover antigo para `.selfsigned.bak`, criar symlink relativo para `-0001`|

---

## BACKUP AUTOMÁTICO

```bash
# Backup diário às 02:00
echo "0 2 * * * deploy bash /opt/ABASE/repo/deploy/hostinger/scripts/backup_now.sh \
  >> /opt/ABASE/logs/backup_cron.log 2>&1" | tee /etc/cron.d/abase-backup
```

Scripts disponíveis em `deploy/hostinger/scripts/`:

|Script|Uso|
|---|---|
|`deploy_prod.sh`|Deploy completo (backup + pull + rebuild)|
|`backup_now.sh`|Backup manual do banco e mídia|
|`rollback.sh <commit>`|Reverter para commit específico|
|`restore_db.sh <arquivo.sql.gz>`|Restaurar banco de dados|
|`restore_files.sh <arquivo.tar.gz>`|Restaurar arquivos de mídia|

---

## CHECKLIST DE DEPLOY

### Infraestrutura

- [ ] VPS Ubuntu 24.04 provisionada
- [ ] Docker + compose plugin instalados
- [ ] UFW ativo (22, 80, 443)
- [ ] Diretórios `/opt/ABASE/` com `chmod 777` em `static` e `media`

### Código

- [ ] Branch `abaseprod` atualizada e enviada
- [ ] `next.config.ts` com `output: "standalone"` em produção
- [ ] Health check `/api/v1/health/` no Django
- [ ] `nginx.conf` com os 3 blocos de Next.js antes do `/api/`

### Configuração

- [ ] `.env.production` criado e preenchido
- [ ] Certificado SSL em `/opt/ABASE/data/certbot/conf/live/`

### Deploy

- [ ] `docker compose up -d --build` OK
- [ ] Todos os 6 containers `healthy`
- [ ] Migrations aplicadas (ver `docker logs abase-backend-prod`)
- [ ] Collectstatic executado (ver logs)

### Dados

- [ ] Banco importado (incluindo tabela `users` com hashes bcrypt)
- [ ] Mídia importada via `upload_media.py`

### Validação

- [ ] `GET /api/v1/health/` → `{"status":"ok"}`
- [ ] `POST /api/auth/login` com credencial real → sucesso
- [ ] Dashboard carrega dados (não zerado)
- [ ] Documentos de associados acessíveis (`/api/media/documentos/...`)
- [ ] Comprovantes de refinanciamento acessíveis (`/api/media/refinanciamentos/...`)

### Operacional

- [ ] Cron de backup configurado
- [ ] Cron de renovação SSL configurado
- [ ] DNS apontando para IP da VPS (para SSL real)
