# ABASE v2 — Guia de Deploy em Produção (Hostinger VPS)

**Domínio**: abasepiaui.cloud
**VPS**: 72.60.58.181 (Ubuntu 24.04 LTS)
**Branch**: abaseprod
**Repositório**: https://github.com/ghitflux/abasenewv2.git

---

## ARQUITETURA DE PRODUÇÃO

```
Internet → Nginx (80/443) → backend (8000, interno)
                          → frontend (3000, interno)
                          → /static/ (volume)
                          → /media/  (volume)
                Backend → MySQL (3306, interno)
                        → Redis (6379, interno)
                Celery  → Redis (broker/resultado)
```

---

## FASE 5 — SEGURANÇA DA VPS

### 5.1. Bootstrap inicial (executar como root)

```bash
ssh root@72.60.58.181

# Atualizar sistema
apt update && apt upgrade -y

# Configurar timezone
timedatectl set-timezone America/Fortaleza

# Instalar utilitários
apt install -y curl git ufw fail2ban ca-certificates gnupg lsb-release unzip jq \
    unattended-upgrades apt-transport-https software-properties-common

# Ativar atualizações automáticas de segurança
dpkg-reconfigure -plow unattended-upgrades
```

### 5.2. Criar usuário deploy

```bash
adduser deploy
usermod -aG sudo deploy
mkdir -p /home/deploy/.ssh
cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys
```

### 5.3. Instalar Docker

```bash
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable docker --now
usermod -aG docker deploy
```

### 5.4. Firewall UFW

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
ufw status
```

### 5.5. Fail2Ban

```bash
systemctl enable fail2ban --now
systemctl status fail2ban
```

### 5.6. ClamAV (antivírus para uploads)

```bash
apt install -y clamav clamav-daemon
freshclam

# Configurar varredura apenas em uploads/media
cat > /etc/cron.daily/clamav-scan << 'EOF'
#!/bin/bash
clamscan -r /opt/ABASE/data/media /opt/ABASE/data/attachments \
    --log=/opt/ABASE/logs/clamav_$(date +%F).log \
    --infected --remove=no 2>&1
EOF
chmod +x /etc/cron.daily/clamav-scan
```

### 5.7. Endurecer SSH (APENAS após validar acesso por chave)

```bash
# ATENÇÃO: Só faça isso depois de confirmar que consegue logar com chave SSH
# Edite /etc/ssh/sshd_config:
sed -i 's/#PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
sed -i 's/#PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh
```

---

## FASE 6 — ESTRUTURA DE DIRETÓRIOS NA VPS

```bash
mkdir -p /opt/ABASE/repo
mkdir -p /opt/ABASE/env
mkdir -p /opt/ABASE/data/{db,redis,media,static,backups/{daily,weekly,monthly},certbot/{conf,www}}
mkdir -p /opt/ABASE/logs
chown -R deploy:deploy /opt/ABASE
```

Estrutura final:
```
/opt/ABASE/
├── repo/          → código do repositório (branch abaseprod)
├── env/           → .env.production (fora do repo)
├── data/
│   ├── db/        → dados do MySQL (volume bind)
│   ├── redis/     → dados do Redis (volume bind)
│   ├── media/     → uploads, comprovantes, anexos
│   ├── static/    → static files Django (collectstatic)
│   ├── backups/   → backups com retenção 7d/4w/3m
│   └── certbot/   → certificados SSL Let's Encrypt
└── logs/          → logs de deploy, backup, restore
```

---

## FASE 7 — SSL COM CERTBOT

### 7.1. Obter certificado (antes de subir nginx com SSL)

```bash
# Subir nginx só com HTTP primeiro (comment o bloco HTTPS temporariamente)
# Depois obter certificado:
docker run --rm \
  -v /opt/ABASE/data/certbot/conf:/etc/letsencrypt \
  -v /opt/ABASE/data/certbot/www:/var/www/certbot \
  certbot/certbot certonly --webroot \
  --webroot-path=/var/www/certbot \
  --email ghitflux@gmail.com \
  --agree-tos \
  --no-eff-email \
  -d abasepiaui.cloud \
  -d www.abasepiaui.cloud
```

### 7.2. Renovação automática

```bash
# Cron job para renovação (a cada 12h)
echo "0 0,12 * * * root docker run --rm -v /opt/ABASE/data/certbot/conf:/etc/letsencrypt -v /opt/ABASE/data/certbot/www:/var/www/certbot certbot/certbot renew --quiet && docker exec abase-nginx-prod nginx -s reload" | tee /etc/cron.d/certbot-renew
```

---

## FASE 11 — DEPLOY REAL

### 11.1. Clonar repositório na VPS

```bash
cd /opt/ABASE
git clone -b abaseprod https://github.com/ghitflux/abasenewv2.git repo
cd repo
git log --oneline -3
```

### 11.2. Criar arquivo de ambiente

```bash
cp /opt/ABASE/repo/deploy/hostinger/.env.production.example /opt/ABASE/env/.env.production
chmod 600 /opt/ABASE/env/.env.production

# EDITAR com valores reais:
nano /opt/ABASE/env/.env.production

# Variáveis obrigatórias a preencher:
# SECRET_KEY          → python3 -c "import secrets; print(secrets.token_urlsafe(64))"
# DATABASE_PASSWORD   → senha forte
# MYSQL_ROOT_PASSWORD → senha forte
# MYSQL_PASSWORD      → igual a DATABASE_PASSWORD
```

### 11.3. Obter certificado SSL (primeira vez)

```bash
# Subir apenas nginx com HTTP para validação ACME
# (ver Fase 7)
```

### 11.4. Executar deploy

```bash
bash /opt/ABASE/repo/deploy/hostinger/scripts/deploy_prod.sh
```

Ou manualmente:

```bash
cd /opt/ABASE/repo
docker compose -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  up -d --build
```

### 11.5. Verificar migrações e static

```bash
# As migrations rodam automaticamente via entrypoint
# Verificar logs:
docker logs abase-backend-prod --tail=50
```

---

## FASE 12 — TESTES FINAIS

```bash
# Status dos containers
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

# Health checks
docker inspect abase-mysql-prod --format '{{.State.Health.Status}}'
docker inspect abase-backend-prod --format '{{.State.Health.Status}}'
docker inspect abase-frontend-prod --format '{{.State.Health.Status}}'

# Logs
docker logs abase-backend-prod --tail=30
docker logs abase-frontend-prod --tail=30
docker logs abase-celery-prod --tail=30
docker logs abase-nginx-prod --tail=20

# Conectividade
curl -I https://abasepiaui.cloud/
curl -s https://abasepiaui.cloud/api/v1/health/
```

---

## COMANDOS RÁPIDOS

| Ação | Comando |
|------|---------|
| Deploy | `bash /opt/ABASE/repo/deploy/hostinger/scripts/deploy_prod.sh` |
| Rollback | `bash /opt/ABASE/repo/deploy/hostinger/scripts/rollback.sh <commit>` |
| Backup manual | `bash /opt/ABASE/repo/deploy/hostinger/scripts/backup_now.sh` |
| Restore banco | `bash /opt/ABASE/repo/deploy/hostinger/scripts/restore_db.sh <arquivo.sql.gz>` |
| Restore media | `bash /opt/ABASE/repo/deploy/hostinger/scripts/restore_files.sh <media.tar.gz>` |
| Ver logs | `docker compose -f /opt/ABASE/repo/deploy/hostinger/docker-compose.prod.yml logs -f` |
| Parar tudo | `docker compose -f /opt/ABASE/repo/deploy/hostinger/docker-compose.prod.yml down` |

---

## BACKUP AUTOMÁTICO (CRON)

```bash
# Backup diário às 02:00
echo "0 2 * * * deploy bash /opt/ABASE/repo/deploy/hostinger/scripts/backup_now.sh >> /opt/ABASE/logs/backup_cron.log 2>&1" | tee /etc/cron.d/abase-backup
```

---

## HOSTINGER DOCKER MANAGER

Para usar o Docker Manager da Hostinger:
- **Compose File URL**: `https://raw.githubusercontent.com/ghitflux/abasenewv2/abaseprod/deploy/hostinger/docker-compose.prod.yml`
- **Serviço de borda pública**: `nginx` (portas 80 e 443)
- **Variáveis de ambiente**: copiar e preencher `.env.production.example`
- **Volumes persistentes**: `mysql_data`, `redis_data`, `backend_media`, `backend_static`

> **NOTA**: O Docker Manager não tem acesso SSH. Use SSH para:
> - Criar diretórios de dados em `/opt/ABASE/`
> - Configurar certificados SSL
> - Rodar scripts de backup e restore

---

## CHECKLIST DE DEPLOY COMPLETO

- [ ] SSH funcional para VPS
- [ ] UFW ativo (22, 80, 443)
- [ ] Fail2Ban ativo
- [ ] Docker instalado e rodando
- [ ] Usuário `deploy` criado com acesso Docker
- [ ] Diretórios `/opt/ABASE/` criados
- [ ] Repositório clonado em `/opt/ABASE/repo` (branch abaseprod)
- [ ] `.env.production` criado e preenchido (fora do repo)
- [ ] Certificado SSL obtido via Certbot
- [ ] `docker compose up -d` executado com sucesso
- [ ] Todos os containers `healthy`
- [ ] `https://abasepiaui.cloud` acessível
- [ ] `https://abasepiaui.cloud/api/v1/health/` retornando `{"status": "ok"}`
- [ ] Login funcional no sistema
- [ ] Upload de arquivos funcional
- [ ] Backup automático configurado (cron)
- [ ] ClamAV configurado para varredura de uploads
