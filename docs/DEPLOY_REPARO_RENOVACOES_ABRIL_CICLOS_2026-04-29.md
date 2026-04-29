# Deploy 2026-04-29 - reparo dos ciclos das renovacoes de abril

## Objetivo

Subir o ajuste do comando `repair_april_effectivated_cycle_materialization`
para reparar renovacoes efetivadas entre `2026-04-01` e `2026-04-28` que nao
materializaram o ciclo destino.

O comando agora tambem cobre contratos em layout manual, onde o rebuild apenas
reconcilia o que ja esta materializado, criando o ciclo destino e as 3 parcelas
previstas quando a renovacao antiga ja esta efetivada.

Nao ha migration neste pacote.

## Arquivo do pacote

- `backend/apps/refinanciamento/management/commands/repair_april_effectivated_cycle_materialization.py`

## Validacao local executada

Auditoria antes do reparo local:

```bash
docker exec abase-v2-backend-1 python manage.py \
  repair_april_effectivated_cycle_materialization \
  --start-date 2026-04-01 --end-date 2026-04-28
```

Resultado: `45` renovacoes auditadas, `5` com problema.

Aplicacao no banco Docker local:

```bash
docker exec abase-v2-backend-1 python manage.py \
  repair_april_effectivated_cycle_materialization \
  --start-date 2026-04-01 --end-date 2026-04-28 --apply
```

Resultado: `5` renovacoes reparadas.

Reauditoria apos o reparo:

```bash
docker exec abase-v2-backend-1 python manage.py \
  repair_april_effectivated_cycle_materialization \
  --start-date 2026-04-01 --end-date 2026-04-28
```

Resultado: `45` renovacoes auditadas, `0` com problema.

Validacao do fluxo novo de efetivacao:

```bash
docker exec abase-v2-backend-1 python manage.py test \
  apps.refinanciamento.tests.test_refinanciamento_pagamentos.RefinanciamentoPagamentosTestCase.test_tesouraria_efetiva_renovacao_com_associado_inadimplente_retorna_para_ativo_e_gera_ciclo_destino \
  --settings=config.settings.testing --noinput
```

Resultado: `1 test OK`.

Check Django:

```bash
docker exec abase-v2-backend-1 python manage.py check
```

Resultado: `System check identified no issues`.

## Deploy via Paramiko com backup agora

Execute a partir da maquina local de deploy.

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

commands = [
    "cd /opt/ABASE/repo && git status --short",
    "cd /opt/ABASE/repo && git rev-parse HEAD",
    "cd /opt/ABASE/repo && bash deploy/hostinger/scripts/backup_now.sh",
    f"cd /opt/ABASE/repo && git fetch origin && git checkout {branch} && git pull --ff-only origin {branch}",
    "cd /opt/ABASE/repo && git rev-parse HEAD",
    f"cd /opt/ABASE/repo && {compose} build backend celery",
    f"cd /opt/ABASE/repo && {compose} up -d --force-recreate --no-deps backend celery",
    f"cd /opt/ABASE/repo && {compose} exec -T backend python manage.py migrate --noinput",
    f"cd /opt/ABASE/repo && {compose} exec -T backend python manage.py check",
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

## Reparo no servidor

Primeiro rode em modo auditoria:

```bash
cd /opt/ABASE/repo

docker compose -p abase \
  --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml \
  exec -T backend python manage.py \
  repair_april_effectivated_cycle_materialization \
  --start-date 2026-04-01 --end-date 2026-04-28
```

Se o resultado listar renovacoes com problema, aplique:

```bash
docker compose -p abase \
  --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml \
  exec -T backend python manage.py \
  repair_april_effectivated_cycle_materialization \
  --start-date 2026-04-01 --end-date 2026-04-28 --apply
```

Reexecute a auditoria sem `--apply`. Resultado esperado:

- `Refinanciamentos auditados`: total de renovacoes efetivadas no periodo;
- `Refinanciamentos com problema: 0`;
- relatorio JSON gravado em `media/relatorios/`.

## Validacao funcional no servidor

Validar uma renovacao efetivada em abril ate `2026-04-28`:

- `Refinanciamento.status=efetivado`;
- `executado_em` e `data_ativacao_ciclo` preenchidos;
- `ciclo_destino` preenchido;
- ciclo destino com 3 parcelas `em_previsao`;
- associado fora da esteira de aptos apos a efetivacao.

Validar uma nova renovacao pela tesouraria:

- anexar comprovante do associado e do agente;
- clicar em efetivar;
- confirmar que o associado fica `Ativo`;
- confirmar que o refinanciamento recebe `ciclo_destino`;
- confirmar que o ciclo destino possui 3 parcelas previstas.

Consulta rapida:

```bash
docker compose -p abase \
  --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml \
  exec -T backend python manage.py shell <<'PY'
from datetime import date

from apps.contratos.models import Parcela
from apps.refinanciamento.models import Refinanciamento

qs = Refinanciamento.objects.filter(
    status=Refinanciamento.Status.EFETIVADO,
    deleted_at__isnull=True,
    executado_em__date__gte=date(2026, 4, 1),
    executado_em__date__lte=date(2026, 4, 28),
).select_related("associado", "contrato_origem", "ciclo_destino")

broken = []
for item in qs:
    parcelas = (
        item.ciclo_destino.parcelas.filter(deleted_at__isnull=True)
        .exclude(status=Parcela.Status.CANCELADO)
        .count()
        if item.ciclo_destino_id
        else 0
    )
    if item.ciclo_destino_id is None or parcelas < 3:
        broken.append((item.id, item.associado.cpf_cnpj, item.ciclo_destino_id, parcelas))

print("renovacoes_efetivadas_periodo", qs.count())
print("renovacoes_sem_ciclo_destino_valido", broken)
PY
```

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
    f"cd /opt/ABASE/repo && {compose} build backend celery",
    f"cd /opt/ABASE/repo && {compose} up -d --force-recreate --no-deps backend celery",
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

Rollback de dados: restaurar o backup gerado antes do `--apply`, caso a
auditoria pos-aplicacao indique divergencia inesperada.
