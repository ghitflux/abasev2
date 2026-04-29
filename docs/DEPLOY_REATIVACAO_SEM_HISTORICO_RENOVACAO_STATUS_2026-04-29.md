# Deploy 2026-04-29 - reativacao sem historico e status pos-renovacao

## Objetivo

Subir a correcao que remove o bloqueio indevido na reativacao de associado
inativo sem contrato anterior local e ajusta a efetivacao de renovacao para
retornar o associado para `ativo` quando a tesouraria materializa o novo ciclo.

## Regras corrigidas

- Reativacao continua permitida apenas para associado `inativo`.
- Reativacao nao exige mais historico anterior de contrato.
- Reativacao ainda bloqueia duplicidade quando ja existe contrato operacional
  aberto para o associado.
- Efetivacao de renovacao na tesouraria passa associado `inadimplente` ou
  `apto_a_renovar` para `ativo` antes da sincronizacao final.
- O ciclo novo da renovacao continua sendo gerado com 3 parcelas previstas.

Nao ha migration neste pacote.

## Arquivos do pacote

- `backend/apps/associados/services.py`
- `backend/apps/associados/tests/test_reactivation.py`
- `backend/apps/refinanciamento/services.py`
- `backend/apps/refinanciamento/tests/test_refinanciamento_pagamentos.py`

## Validacao local executada

```bash
docker exec abase-v2-backend-1 python -m py_compile \
  apps/associados/services.py \
  apps/associados/tests/test_reactivation.py \
  apps/refinanciamento/services.py \
  apps/refinanciamento/tests/test_refinanciamento_pagamentos.py
```

Resultado: sem erro.

```bash
docker exec abase-v2-backend-1 python manage.py test \
  apps.associados.tests.test_reactivation \
  --settings=config.settings.testing --noinput
```

Resultado: `8 tests OK`.

```bash
docker exec abase-v2-backend-1 python manage.py test \
  apps.refinanciamento.tests.test_refinanciamento_pagamentos.RefinanciamentoPagamentosTestCase.test_tesouraria_efetiva_renovacao_com_associado_inadimplente_retorna_para_ativo_e_gera_ciclo_destino \
  --settings=config.settings.testing --noinput
```

Resultado: `1 test OK`.

Tambem foi validado localmente o fluxo completo do CPF `77852621368` com
rollback: a renovacao criou ciclo 2 com 3 parcelas, mudou o associado para
`ativo` e nao permaneceu como `apto_a_renovar`.

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

## Validacao no servidor

### Reativacao sem historico anterior

Depois do deploy, use a tela do associado inativo que antes retornava:

`A reativacao exige historico anterior de contrato para este associado.`

Resultado esperado:

- a mensagem nao deve aparecer;
- a reativacao deve criar um contrato com `origem_operacional=reativacao`;
- o associado deve ir para `em_analise`;
- a linha deve aparecer na analise/tesouraria conforme aprovacao.

Checagem por shell, se necessario:

```bash
cd /opt/ABASE/repo

docker compose -p abase \
  --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml \
  exec -T backend python manage.py shell <<'PY'
from apps.associados.models import Associado
from apps.contratos.models import Contrato

nome = "MARCELO BRITO DE OLIVEIRA"
a = Associado.objects.filter(nome_completo__icontains=nome).first()
if not a:
    raise SystemExit("Associado nao encontrado")

open_operational = a.contratos.filter(
    deleted_at__isnull=True,
    contrato_canonico__isnull=True,
).exclude(
    status__in=[Contrato.Status.CANCELADO, Contrato.Status.ENCERRADO]
).exists()

print("associado", a.id, a.nome_completo, a.cpf_cnpj, a.status)
print("contratos_ativos_local", a.contratos.filter(deleted_at__isnull=True).count())
print("possui_contrato_operacional_aberto", open_operational)
PY
```

Se `possui_contrato_operacional_aberto=True`, o bloqueio restante e esperado:
ele evita criar duas reativacoes ou contratos operacionais simultaneos.

### Renovacao efetivada

Validar em um caso de renovacao efetivada pela tesouraria:

- `Refinanciamento.status=efetivado`;
- `executado_em` preenchido;
- `data_ativacao_ciclo` preenchida;
- `ciclo_destino` criado;
- associado com `status=ativo`;
- associado fora da esteira de aptos.

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

Como nao ha migration, rollback de codigo basta para desfazer a regra nova.
