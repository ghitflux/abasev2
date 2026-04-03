# Setup Completo de Produção em `abasepiaui.com` — 03/04/2026

## Objetivo

Preparar um deploy completo em uma VPS de produção para `abasepiaui.com`, reaproveitando a stack atual da Hostinger, mas já com:

- domínio novo `.com`
- API web em `https://abasepiaui.com/api/v1`
- app mobile apontando para o domínio novo
- fluxo preparado para build iOS via Expo EAS

## 1. Ajustes de código antes do primeiro deploy

### Web e backend

Trocar as referências de domínio nestes pontos:

- `deploy/hostinger/nginx/nginx.conf`
- `deploy/hostinger/docker-compose.prod.yml`
- `deploy/hostinger/.env.production.example`

Trocas mínimas:

- `abasepiaui.cloud` → `abasepiaui.com`
- `www.abasepiaui.cloud` → `www.abasepiaui.com`
- `https://abasepiaui.cloud/api/v1` → `https://abasepiaui.com/api/v1`

### App mobile Expo

Pontos que hoje apontam para `.cloud`:

- `abase_mobile_new/.env`
- `abase_mobile_new/eas.json`
- `abase_mobile_new/src/services/api/constants.ts`

Troca alvo:

```env
EXPO_PUBLIC_API_BASE_URL=https://abasepiaui.com/api/v1
```

### App mobile legado

Se o app legado ainda estiver em operação, revisar também:

- `abase_mobile/Abase_mobile_legado/abasev2app/.env`
- chaves `API_URL`, `LOGIN_API_URL`, `REGISTER_API_URL` e correlatas

Base nova:

```env
API_URL=https://abasepiaui.com/api
```

## 2. Bootstrap da VPS

Fluxo base igual ao da Hostinger atual:

```bash
ssh root@<IP_VPS>
apt update && apt upgrade -y
timedatectl set-timezone America/Fortaleza
apt install -y curl git ufw fail2ban ca-certificates gnupg lsb-release unzip apt-transport-https software-properties-common netcat-openbsd
```

Usuário e Docker:

```bash
adduser deploy
usermod -aG sudo deploy
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable docker --now
usermod -aG docker deploy
```

Firewall e diretórios:

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable

mkdir -p /opt/ABASE/{repo,env,logs}
mkdir -p /opt/ABASE/data/{db,redis,media,static,certbot/{conf,www}}
chown -R deploy:deploy /opt/ABASE
chmod 777 /opt/ABASE/data/media /opt/ABASE/data/static
```

## 3. Clonar e configurar

```bash
cd /opt/ABASE
git clone -b abaseprod https://github.com/ghitflux/abasenewv2.git repo
cp /opt/ABASE/repo/deploy/hostinger/.env.production.example /opt/ABASE/env/.env.production
chmod 600 /opt/ABASE/env/.env.production
nano /opt/ABASE/env/.env.production
```

Conteúdo mínimo para `abasepiaui.com`:

```env
DJANGO_SETTINGS_MODULE=config.settings.production
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
```

## 4. Nginx e SSL

Antes do primeiro `up`, o `nginx.conf` precisa estar com:

- `server_name abasepiaui.com www.abasepiaui.com;`
- certificado em `/etc/letsencrypt/live/abasepiaui.com/`

Se o DNS ainda não tiver propagado, usar certificado temporário:

```bash
mkdir -p /opt/ABASE/data/certbot/conf/live/abasepiaui.com
openssl req -x509 -nodes -newkey rsa:4096 -days 365 \
  -keyout /opt/ABASE/data/certbot/conf/live/abasepiaui.com/privkey.pem \
  -out /opt/ABASE/data/certbot/conf/live/abasepiaui.com/fullchain.pem \
  -subj "/CN=abasepiaui.com"
cp /opt/ABASE/data/certbot/conf/live/abasepiaui.com/fullchain.pem \
  /opt/ABASE/data/certbot/conf/live/abasepiaui.com/chain.pem
```

Depois do DNS:

```bash
docker compose -p abase --env-file /opt/ABASE/env/.env.production -f deploy/hostinger/docker-compose.prod.yml up -d nginx
docker run --rm -it \
  -v /opt/ABASE/data/certbot/conf:/etc/letsencrypt \
  -v /opt/ABASE/data/certbot/www:/var/www/certbot \
  certbot/certbot certonly --webroot \
  -w /var/www/certbot \
  -d abasepiaui.com -d www.abasepiaui.com
```

## 5. Primeiro deploy

```bash
cd /opt/ABASE/repo
docker compose -p abase --env-file /opt/ABASE/env/.env.production -f deploy/hostinger/docker-compose.prod.yml build backend frontend
docker compose -p abase --env-file /opt/ABASE/env/.env.production -f deploy/hostinger/docker-compose.prod.yml up -d
docker compose -p abase --env-file /opt/ABASE/env/.env.production -f deploy/hostinger/docker-compose.prod.yml exec -T backend python manage.py migrate
docker compose -p abase --env-file /opt/ABASE/env/.env.production -f deploy/hostinger/docker-compose.prod.yml exec -T backend python manage.py check
```

Validação:

```bash
curl -fsS https://abasepiaui.com/api/v1/health/
curl -I https://abasepiaui.com/login
curl -I https://abasepiaui.com/api/v1/auth/login/
```

## 6. Ajuste do app mobile para o domínio novo

### `abase_mobile_new`

Atualizar:

- `abase_mobile_new/.env`
- `abase_mobile_new/eas.json`
- `abase_mobile_new/src/services/api/constants.ts`

Valor alvo:

```env
EXPO_PUBLIC_API_BASE_URL=https://abasepiaui.com/api/v1
```

Revalidar localmente:

```bash
cd /mnt/d/apps/abasev2/abasev2/abase_mobile_new
npm ci
npx expo install --check
```

### Se o legado continuar em produção

Atualizar o `.env` do app legado com `https://abasepiaui.com/api`.

## 7. Build iOS via Expo EAS

O projeto já está estruturalmente apto:

- `abase_mobile_new/app.json` já tem `ios.bundleIdentifier=br.org.abase.mobile`
- `abase_mobile_new/app.json` já tem `owner` e `projectId`
- `abase_mobile_new/eas.json` já possui profiles reutilizáveis
- `abase_mobile_new/package.json` agora expõe atalhos de build e submit iOS

Pré-requisitos externos:

- conta Expo autenticada
- conta Apple Developer ativa
- app criado no App Store Connect para `br.org.abase.mobile`

Comandos:

```bash
cd /mnt/d/apps/abasev2/abasev2/abase_mobile_new
npm ci
eas login
eas whoami
npm run eas:build:ios:preview
npm run eas:build:ios:production
npm run eas:submit:ios:production
```

Observações:

- `preview` é o perfil mais seguro para validar distribuição interna
- `production` gera build de loja
- antes do primeiro build iOS, confirme no Expo Dashboard se o projeto segue no owner `helciovenancio`
- se o backend oficial passar a ser `.com`, não deixar fallback antigo em `.cloud`

## 8. Regra operacional para a nova VPS

- não copiar `backups/`, `dumps_legado/`, `anexos_legado/` nem `media/` inteira para a máquina
- se for necessário subir mídia, usar apenas delta controlado
- manter `/opt/ABASE/data/media` e `/opt/ABASE/data/static` como storage persistente
- manter o repositório limpo; nada de dumps ou tarballs em `/opt/ABASE/repo`
