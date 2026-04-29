# Deploy 2026-04-29 - reativacao paga e reparo Jarlene

## Objetivo

Subir o pacote que corrige a regra de reativacao paga e executar o reparo
pontual da associada `JARLENE MARIA RIBEIRO RODRIGUES`, CPF
`025.000.113-64`, cuja reativacao ja foi paga no servidor.

O mesmo deploy tambem deve remover o bloqueio temporario do app mobile no
servidor, deixando `APP_MAINTENANCE_MODE=false` para que associados voltem a
logar normalmente.

## Regras corrigidas

- Contrato antigo pago de associado reativado nao deve ir para `cancelado`.
- Contrato antigo pago deve ficar como historico encerrado.
- Efetivacao de reativacao deve materializar o ciclo novo mesmo quando a UI nao
  envia `competencias_ciclo`.
- Associado reativado e pago deve voltar para `ativo`.
- Novos anexos de reativacao/efetivacao nao sobrescrevem anexos antigos.
- Todos os comprovantes vinculados ao contrato/ciclo devem permanecer visiveis.

Nao ha migration neste pacote.

## Arquivos do pacote

- `backend/apps/associados/services.py`
- `backend/apps/associados/tests/test_reactivation.py`
- `backend/apps/associados/management/commands/repair_paid_reactivation.py`
- `backend/apps/tesouraria/services.py`

## Validacao local executada

```bash
docker exec abase-v2-backend-1 python -m py_compile \
  apps/associados/services.py \
  apps/tesouraria/services.py \
  apps/associados/tests/test_reactivation.py \
  apps/associados/management/commands/repair_paid_reactivation.py
```

Resultado: sem erro.

```bash
docker exec abase-v2-backend-1 python manage.py test \
  apps.associados.tests.test_reactivation \
  --settings=config.settings.testing --noinput
```

Resultado: `7 tests OK`.

```bash
docker exec abase-v2-backend-1 python manage.py test \
  apps.tesouraria.tests.test_fluxo_completo.TestFluxoCompleto.test_tesouraria_serializer_expoe_evidencias_canonicas_nos_comprovantes \
  apps.tesouraria.tests.test_fluxo_completo.TestFluxoCompleto.test_substituir_comprovante_nao_efetiva_sem_acao_explicita \
  apps.tesouraria.tests.test_fluxo_completo.TestFluxoCompleto.test_efetivacao_com_comprovantes_ja_anexados_exige_acao_explicita \
  apps.tesouraria.tests.test_fluxo_completo.TestFluxoCompleto.test_tesouraria_pode_devolver_reativacao_para_analise \
  apps.tesouraria.tests.test_fluxo_completo.TestFluxoCompleto.test_remover_reativacao_antiga_nao_remove_reativacao_atual_da_tesouraria \
  --settings=config.settings.testing --noinput
```

Resultado: `5 tests OK`.

```bash
docker exec abase-v2-backend-1 python manage.py help repair_paid_reactivation
docker exec abase-v2-backend-1 python manage.py repair_paid_reactivation \
  --cpf 025.000.113-64 \
  --contract-id 450 \
  --cycle-start 2026-04
```

Resultado: comando disponivel e dry-run executado sem alterar dados locais.

## Deploy via Paramiko com backup agora

Execute a partir da maquina local de deploy. O script para se houver alteracoes
locais no servidor antes de atualizar.

```bash
python -m pip install paramiko

export ABASE_HOST="IP_OU_HOST_DO_SERVIDOR"
export ABASE_USER="USUARIO_SSH"
export ABASE_KEY="/caminho/para/chave_ssh"
export ABASE_BRANCH="abaseprod"
```

```bash
python - <<'PY'
import os
import sys
import paramiko

host = os.environ["ABASE_HOST"]
user = os.environ["ABASE_USER"]
key_path = os.environ["ABASE_KEY"]
branch = os.environ.get("ABASE_BRANCH", "abaseprod")

compose = (
    "docker compose -p abase "
    "--env-file /opt/ABASE/env/.env.production "
    "-f deploy/hostinger/docker-compose.prod.yml"
)

disable_mobile_maintenance = r"""
python3 - <<'PY'
from datetime import datetime
from pathlib import Path
import shutil

env_path = Path("/opt/ABASE/env/.env.production")
backup_path = env_path.with_name(
    env_path.name + f".mobile-unblock-{datetime.now():%Y%m%d%H%M%S}.bak"
)
shutil.copy2(env_path, backup_path)

lines = env_path.read_text().splitlines()
updated = []
seen = False

for line in lines:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in line:
        updated.append(line)
        continue

    key = line.split("=", 1)[0].strip()
    if key == "APP_MAINTENANCE_MODE":
        updated.append("APP_MAINTENANCE_MODE=false")
        seen = True
    else:
        updated.append(line)

if not seen:
    updated.append("APP_MAINTENANCE_MODE=false")

env_path.write_text("\n".join(updated) + "\n")
print(f"Backup env: {backup_path}")
print("APP_MAINTENANCE_MODE=false")
PY
""".strip()

commands = [
    "cd /opt/ABASE/repo && git status --short",
    "cd /opt/ABASE/repo && git rev-parse HEAD",
    "cd /opt/ABASE/repo && bash deploy/hostinger/scripts/backup_now.sh",
    disable_mobile_maintenance,
    f"cd /opt/ABASE/repo && git fetch origin && git checkout {branch} && git pull --ff-only origin {branch}",
    "cd /opt/ABASE/repo && git rev-parse HEAD",
    f"cd /opt/ABASE/repo && {compose} build backend frontend celery",
    f"cd /opt/ABASE/repo && {compose} up -d --force-recreate backend frontend celery",
    f"cd /opt/ABASE/repo && {compose} exec -T backend python manage.py migrate --noinput",
    f"cd /opt/ABASE/repo && {compose} exec -T backend python manage.py check",
    f"cd /opt/ABASE/repo && {compose} exec -T backend python manage.py shell -c \"from django.conf import settings; print('APP_MAINTENANCE_MODE=', settings.APP_MAINTENANCE_MODE)\"",
    f"cd /opt/ABASE/repo && {compose} ps",
]

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname=host, username=user, key_filename=key_path, timeout=30)

try:
    for index, command in enumerate(commands):
        print(f"\n$ {command}", flush=True)
        stdin, stdout, stderr = client.exec_command(command, get_pty=True)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        status = stdout.channel.recv_exit_status()
        if out:
            print(out, end="")
        if err:
            print(err, end="", file=sys.stderr)
        if status != 0:
            raise SystemExit(f"Comando falhou com status {status}: {command}")
        if index == 0 and out.strip():
            raise SystemExit(
                "Servidor possui alteracoes locais. Interrompa o deploy e salve o diff."
            )
finally:
    client.close()
PY
```

## Desbloqueio do app mobile

O bloqueio implantado no servidor e controlado por `APP_MAINTENANCE_MODE`.
Com `true`, o backend retorna `503` para login/uso do app mobile legado e para
os endpoints `/api/v1/app/*`. Para liberar o app, a flag precisa ficar `false`
e o backend precisa ser recriado para reler o `.env.production`.

O script de deploy acima ja faz esse ajuste e cria backup do arquivo de env em
`/opt/ABASE/env/.env.production.mobile-unblock-YYYYMMDDHHMMSS.bak`. Para fazer
apenas o desbloqueio, sem subir codigo, execute:

```bash
python - <<'PY'
import os
import sys
import paramiko

host = os.environ["ABASE_HOST"]
user = os.environ["ABASE_USER"]
key_path = os.environ["ABASE_KEY"]

compose = (
    "docker compose -p abase "
    "--env-file /opt/ABASE/env/.env.production "
    "-f /opt/ABASE/repo/deploy/hostinger/docker-compose.prod.yml"
)

commands = [
    r"""
python3 - <<'REMOTE'
from datetime import datetime
from pathlib import Path
import shutil

env_path = Path("/opt/ABASE/env/.env.production")
backup_path = env_path.with_name(
    env_path.name + f".mobile-unblock-{datetime.now():%Y%m%d%H%M%S}.bak"
)
shutil.copy2(env_path, backup_path)

lines = env_path.read_text().splitlines()
updated = []
seen = False

for line in lines:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in line:
        updated.append(line)
        continue

    key = line.split("=", 1)[0].strip()
    if key == "APP_MAINTENANCE_MODE":
        updated.append("APP_MAINTENANCE_MODE=false")
        seen = True
    else:
        updated.append(line)

if not seen:
    updated.append("APP_MAINTENANCE_MODE=false")

env_path.write_text("\n".join(updated) + "\n")
print(f"Backup env: {backup_path}")
print("APP_MAINTENANCE_MODE=false")
REMOTE
""".strip(),
    f"{compose} up -d --force-recreate --no-deps backend celery",
    f"{compose} exec -T backend python manage.py shell -c \"from django.conf import settings; print('APP_MAINTENANCE_MODE=', settings.APP_MAINTENANCE_MODE)\"",
    "curl -fsS https://abasepiaui.com/api/v1/app/status/",
]

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname=host, username=user, key_filename=key_path, timeout=30)

try:
    for command in commands:
        print(f"\n$ {command}", flush=True)
        stdin, stdout, stderr = client.exec_command(command, get_pty=True)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        status = stdout.channel.recv_exit_status()
        if out:
            print(out, end="")
        if err:
            print(err, end="", file=sys.stderr)
        if status != 0:
            raise SystemExit(f"Comando falhou com status {status}: {command}")
finally:
    client.close()
PY
```

Validacao esperada:

- `manage.py shell` imprime `APP_MAINTENANCE_MODE= False`.
- `GET https://abasepiaui.com/api/v1/app/status/` retorna
  `"maintenance": false`.
- `POST /api/login` e `POST /api/v1/auth/login/` nao devem mais retornar
  `503` com codigo `mobile_maintenance`.

## Reparo da Jarlene no servidor

Depois do deploy, rode primeiro o dry-run:

```bash
cd /opt/ABASE/repo

docker compose -p abase \
  --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml \
  exec -T backend python manage.py repair_paid_reactivation \
  --cpf 025.000.113-64 \
  --contract-code CTR-20260428185740-A8109A \
  --cycle-start 2026-04
```

Conferir no dry-run:

- `contrato_reativacao` deve ser `CTR-20260428185740-A8109A`;
- `contratos_antigos_para_historico` deve listar o contrato antigo pago;
- `novo_ciclo` deve listar `2026-04-01, 2026-05-01, 2026-06-01`;
- `comprovantes_preservados` deve listar os anexos enviados.

Se o dry-run estiver correto, aplique:

```bash
docker compose -p abase \
  --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml \
  exec -T backend python manage.py repair_paid_reactivation \
  --cpf 025.000.113-64 \
  --contract-code CTR-20260428185740-A8109A \
  --cycle-start 2026-04 \
  --apply
```

## Validacao pos-reparo

```bash
docker compose -p abase \
  --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml \
  exec -T backend python manage.py shell <<'PY'
from apps.associados.models import Associado
from apps.contratos.cycle_projection import build_contract_cycle_projection, resolve_associado_mother_status
from apps.contratos.models import Parcela
from apps.refinanciamento.models import Comprovante

cpf = "025.000.113-64"
a = Associado.objects.filter(cpf_cnpj__in=[cpf, "02500011364"]).first()
print("ASSOCIADO", a.id, a.nome_completo, a.status, resolve_associado_mother_status(a))

for c in a.contratos.filter(deleted_at__isnull=True).order_by("id"):
    projection = build_contract_cycle_projection(c)
    print("CONTRATO", c.id, c.codigo, c.status, c.origem_operacional, c.auxilio_liberado_em, projection.get("status_renovacao"))
    print("CICLOS", list(c.ciclos.filter(deleted_at__isnull=True).order_by("numero").values_list("id", "numero", "status", "data_inicio", "data_fim")))
    print("PARCELAS", list(Parcela.objects.filter(ciclo__contrato=c).order_by("referencia_mes").values_list("referencia_mes", "status")))
    print("COMPROVANTES", list(Comprovante.objects.filter(contrato=c, deleted_at__isnull=True).order_by("id").values_list("id", "papel", "tipo", "origem", "ciclo_id", "nome_original")))
PY
```

Resultado esperado:

- associado com `status_db=ativo` e `status_resolvido=ativo`;
- contrato antigo pago com `status=encerrado`, nao `cancelado`;
- contrato `CTR-20260428185740-A8109A` com `status=ativo`;
- novo ciclo com abril/2026, maio/2026 e junho/2026;
- comprovantes preservados e vinculados ao contrato/ciclo.

## Rollback

Rollback de codigo:

```bash
export ABASE_ROLLBACK_SHA="SHA_ANTERIOR_VALIDADO"

python - <<'PY'
import os
import sys
import paramiko

host = os.environ["ABASE_HOST"]
user = os.environ["ABASE_USER"]
key_path = os.environ["ABASE_KEY"]
sha = os.environ["ABASE_ROLLBACK_SHA"]

compose = (
    "docker compose -p abase "
    "--env-file /opt/ABASE/env/.env.production "
    "-f deploy/hostinger/docker-compose.prod.yml"
)

commands = [
    "cd /opt/ABASE/repo && git rev-parse HEAD",
    "cd /opt/ABASE/repo && bash deploy/hostinger/scripts/backup_now.sh",
    f"cd /opt/ABASE/repo && git checkout {sha}",
    f"cd /opt/ABASE/repo && {compose} build backend frontend celery",
    f"cd /opt/ABASE/repo && {compose} up -d backend frontend celery",
    f"cd /opt/ABASE/repo && {compose} exec -T backend python manage.py migrate --noinput",
    f"cd /opt/ABASE/repo && {compose} exec -T backend python manage.py check",
    f"cd /opt/ABASE/repo && {compose} ps",
]

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname=host, username=user, key_filename=key_path, timeout=30)

try:
    for command in commands:
        print(f"\n$ {command}", flush=True)
        stdin, stdout, stderr = client.exec_command(command, get_pty=True)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        status = stdout.channel.recv_exit_status()
        if out:
            print(out, end="")
        if err:
            print(err, end="", file=sys.stderr)
        if status != 0:
            raise SystemExit(f"Comando falhou com status {status}: {command}")
finally:
    client.close()
PY
```

Se o comando `repair_paid_reactivation --apply` ja foi executado, rollback de
dados deve ser por restore do backup criado antes do deploy, porque a correcao
altera status, ciclos e vinculos de comprovantes da Jarlene.

Para reativar o bloqueio mobile em rollback operacional, restaure a linha
`APP_MAINTENANCE_MODE=true` no `/opt/ABASE/env/.env.production` ou volte o
backup `.mobile-unblock-*` e recrie `backend`/`celery` com `--force-recreate`.
