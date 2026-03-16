# Deploy na VPS Hostinger com Docker, SSL e restauração completa

## Objetivo
- Publicar a aplicação usando o repositório GitHub atual.
- Rodar `frontend`, `backend`, `mysql`, `redis` e `celery` em Docker.
- Manter anexos e comprovantes no volume oficial `backend_media`.
- Restaurar banco de dados, anexos e comprovantes.
- Proteger a VPS com hardening mínimo obrigatório.
- Usar o domínio com SSL válido.
- Deixar o fluxo compatível para execução remota via Claude Code + Paramiko.

## Arquitetura recomendada
- `nginx` no host da VPS terminando SSL em `443`.
- `frontend` em Docker ouvindo apenas em `127.0.0.1:3000`.
- `backend` em Docker ouvindo apenas em `127.0.0.1:8000`.
- `mysql`, `redis` e `celery` sem exposição pública.
- O navegador acessa apenas o domínio público.
- A UI abre anexos por `/api/media/...`, então o backend não precisa ser exposto diretamente na internet.

## Pré-requisitos
- VPS Ubuntu 24.04 LTS ou Debian 12 com acesso `root`.
- Domínio apontando para o IP da VPS.
- Repositório GitHub acessível por deploy key ou token.
- Dump do banco MySQL já exportado.
- Acervo `backend/media` ou pacote com anexos e comprovantes já sincronizados.

## 1. Bootstrap inicial da VPS
Execute como `root`:

```bash
apt update && apt upgrade -y
timedatectl set-timezone America/Fortaleza
apt install -y curl git ufw fail2ban ca-certificates gnupg lsb-release unzip jq
apt install -y unattended-upgrades apt-transport-https software-properties-common
dpkg-reconfigure -plow unattended-upgrades
```

## 2. Segurança mínima obrigatória
### SSH
- Cadastrar sua chave pública.
- Desabilitar login por senha.
- Depois do bootstrap, preferir um usuário `deploy` com `sudo`.

Exemplo:

```bash
adduser deploy
usermod -aG sudo deploy
mkdir -p /home/deploy/.ssh
cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys
```

Edite `/etc/ssh/sshd_config`:

```text
PermitRootLogin prohibit-password
PasswordAuthentication no
PubkeyAuthentication yes
X11Forwarding no
```

Depois:

```bash
systemctl restart ssh
```

### Firewall

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

### Fail2ban

```bash
systemctl enable fail2ban --now
```

## 3. Instalação do Docker

```bash
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable docker --now
usermod -aG docker deploy
```

## 4. Estrutura de diretórios

```bash
mkdir -p /opt/abasev2
mkdir -p /opt/abasev2/releases
mkdir -p /opt/abasev2/shared/backups
mkdir -p /opt/abasev2/shared/import
mkdir -p /opt/abasev2/shared/nginx
```

## 5. Clone do repositório
Use deploy key ou token.

```bash
cd /opt/abasev2
git clone git@github.com:SEU_USUARIO/SEU_REPO.git app
cd app
git checkout main
```

## 6. Arquivo de ambiente de produção
Criar `.env.production` no servidor:

```dotenv
DJANGO_SETTINGS_MODULE=config.settings.production
DEBUG=False
SECRET_KEY=troque-isto
DATABASE_NAME=abase_v2
DATABASE_USER=abase
DATABASE_PASSWORD=troque-isto
DATABASE_HOST=mysql
DATABASE_PORT=3306
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2
NEXT_PUBLIC_API_URL=https://SEU_DOMINIO/api/v1
INTERNAL_API_URL=http://backend:8000/api/v1
ALLOWED_HOSTS=SEU_DOMINIO,www.SEU_DOMINIO
CSRF_TRUSTED_ORIGINS=https://SEU_DOMINIO,https://www.SEU_DOMINIO
```

## 7. Ajuste operacional de portas para produção
No deploy, mantenha somente o `frontend` acessível pelo host. O ideal é:
- `frontend`: `127.0.0.1:3000:3000`
- `backend`: `127.0.0.1:8000:8000`
- sem portas públicas para `mysql` e `redis`

Se necessário, mantenha isso em um `docker-compose.prod.yml`.

## 8. Subir a stack

```bash
cd /opt/abasev2/app
cp .env.production .env
docker compose pull
docker compose up -d --build
docker compose ps
```

## 9. Restore do banco de dados
Copie o dump para `/opt/abasev2/shared/import/abase.sql` e execute:

```bash
cd /opt/abasev2/app
docker compose exec -T mysql mysql -u"$DATABASE_USER" -p"$DATABASE_PASSWORD" "$DATABASE_NAME" < /opt/abasev2/shared/import/abase.sql
```

Se preferir via host:

```bash
docker compose exec -T mysql sh -lc 'mysql -u"$DATABASE_USER" -p"$DATABASE_PASSWORD" "$DATABASE_NAME"' < /opt/abasev2/shared/import/abase.sql
```

## 10. Restore dos anexos e comprovantes
Empacote localmente:

```bash
tar -C backend/media -czf backend-media.tar.gz .
```

Envie para a VPS em `/opt/abasev2/shared/import/backend-media.tar.gz` e restaure no volume oficial:

```bash
mkdir -p /opt/abasev2/shared/import/backend-media
tar -xzf /opt/abasev2/shared/import/backend-media.tar.gz -C /opt/abasev2/shared/import/backend-media
docker run --rm \
  -v abasev2_backend_media:/target \
  -v /opt/abasev2/shared/import/backend-media:/source:ro \
  alpine sh -c "cp -a /source/. /target/"
```

Se o nome do projeto Docker mudar, ajuste o nome do volume com `docker volume ls`.

## 11. Migrações e checks

```bash
cd /opt/abasev2/app
docker compose exec -T backend python manage.py migrate
docker compose exec -T backend python manage.py check
docker compose exec -T backend python manage.py collectstatic --noinput
```

## 12. Nginx com proxy reverso
Exemplo de `/etc/nginx/sites-available/abasev2.conf`:

```nginx
server {
    listen 80;
    server_name SEU_DOMINIO www.SEU_DOMINIO;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Ative:

```bash
ln -s /etc/nginx/sites-available/abasev2.conf /etc/nginx/sites-enabled/abasev2.conf
nginx -t
systemctl reload nginx
```

## 13. SSL com Certbot

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d SEU_DOMINIO -d www.SEU_DOMINIO
systemctl enable certbot.timer
```

## 14. Verificações finais

```bash
curl -I https://SEU_DOMINIO
curl -I https://SEU_DOMINIO/api/v1/auth/me/
docker compose ps
docker compose logs backend --tail=100
docker compose logs frontend --tail=100
docker compose logs celery --tail=100
```

Validar também:
- login no sistema
- abertura local de anexos em `/api/media/...`
- páginas de associados, pagamentos e refinanciamentos
- importação e relatórios principais

## 15. Backups recorrentes
### Banco

```bash
docker compose exec -T mysql sh -lc 'mysqldump -u"$DATABASE_USER" -p"$DATABASE_PASSWORD" "$DATABASE_NAME"' > /opt/abasev2/shared/backups/abase_$(date +%F_%H%M).sql
```

### Mídia

```bash
docker run --rm \
  -v abasev2_backend_media:/source \
  -v /opt/abasev2/shared/backups:/backup \
  alpine sh -c 'cd /source && tar -czf /backup/media_$(date +%F_%H%M).tar.gz .'
```

## 16. Fluxo recomendado com Claude Code + Paramiko
Use o acesso `root` apenas para bootstrap inicial. Depois disso:
1. Claude Code conecta via Paramiko.
2. Atualiza o repositório com `git fetch` e `git checkout`.
3. Sincroniza `.env.production`.
4. Executa `docker compose up -d --build`.
5. Executa migrações e checks.
6. Se houver import de banco/mídia, envia os artefatos para `/opt/abasev2/shared/import`.
7. Roda restore do MySQL e restore do volume `backend_media`.
8. Valida `curl`, `docker compose ps` e logs.

## 17. Observações de segurança
- Não exponha `mysql` nem `redis` publicamente.
- Não mantenha `DEBUG=True` em produção.
- Não mantenha `root` com senha habilitada.
- Guarde `SECRET_KEY`, credenciais do banco e tokens GitHub fora do repositório.
- Faça backup antes de qualquer restore.
- Use HTTPS obrigatório.
