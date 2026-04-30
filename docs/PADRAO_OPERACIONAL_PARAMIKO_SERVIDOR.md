# Padrao operacional - atualizacoes e acoes no servidor via Paramiko

## Decisao operacional

Paramiko passa a ser o padrao para atualizacoes, reparos, validacoes e
rollbacks no servidor do ABASE.

O objetivo e manter toda acao remota reproduzivel, registrada no terminal local
e executada em sequencia controlada, sem depender de uma sessao SSH manual.

## Quando usar

Usar Paramiko para:

- deploy de codigo;
- execucao de migrations;
- reinicio de containers;
- backups antes de alteracoes;
- comandos de reparo com `manage.py`;
- validacoes de banco;
- rollback por SHA;
- consultas operacionais que precisam ser registradas junto do deploy.

SSH manual fica restrito a investigacao emergencial, leitura simples ou
recuperacao quando a automacao por Paramiko nao conseguir conectar.

## Variaveis locais padrao

```bash
python -m pip install paramiko

export ABASE_HOST="IP_OU_HOST_DO_SERVIDOR"
export ABASE_USER="USUARIO_SSH"
export ABASE_KEY="/caminho/para/chave_ssh"
export ABASE_BRANCH="abaseprod"
```

## Sequencia obrigatoria de atualizacao

Todo deploy deve seguir esta ordem:

1. Verificar `git status --short` no servidor.
2. Interromper se houver alteracao local nao versionada.
3. Registrar `git rev-parse HEAD` antes do deploy.
4. Executar backup agora.
5. Atualizar o branch com `git fetch`, `git checkout` e `git pull --ff-only`.
6. Registrar o novo `git rev-parse HEAD`.
7. Build/recreate dos servicos afetados.
8. Executar `migrate --noinput`.
9. Executar `manage.py check`.
10. Executar validacoes especificas do pacote.
11. Registrar `docker compose ps`.

## Template de deploy por Paramiko

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

## Template de acao operacional

Use este formato para comandos pontuais, como reparos de dados ou auditorias.

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
    "-f deploy/hostinger/docker-compose.prod.yml"
)

commands = [
    "cd /opt/ABASE/repo && git rev-parse HEAD",
    "cd /opt/ABASE/repo && bash deploy/hostinger/scripts/backup_now.sh",
    f"cd /opt/ABASE/repo && {compose} exec -T backend python manage.py check",
    # Adicione aqui o comando operacional, por exemplo:
    # f"cd /opt/ABASE/repo && {compose} exec -T backend python manage.py comando --dry-run",
    # f"cd /opt/ABASE/repo && {compose} exec -T backend python manage.py comando --apply",
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

## Regras de seguranca

- Sempre fazer backup antes de comando que altera banco, arquivos ou containers.
- Sempre rodar primeiro em modo auditoria quando o comando oferecer `--dry-run`
  ou quando `--apply` for opcional.
- Nunca continuar deploy se `git status --short` do servidor retornar algo.
- Usar `git pull --ff-only`; nao usar merge manual no servidor.
- Usar rollback por SHA conhecido, nao por branch movel.
- Registrar no documento do pacote os comandos executados e o resultado esperado.

## Rollback padrao

```bash
export ABASE_ROLLBACK_SHA="SHA_ANTERIOR_VALIDADO"
```

Usar o mesmo template Paramiko, trocando a sequencia central por:

```bash
cd /opt/ABASE/repo && bash deploy/hostinger/scripts/backup_now.sh
cd /opt/ABASE/repo && git checkout "$ABASE_ROLLBACK_SHA"
cd /opt/ABASE/repo && docker compose -p abase --env-file /opt/ABASE/env/.env.production -f deploy/hostinger/docker-compose.prod.yml build backend celery
cd /opt/ABASE/repo && docker compose -p abase --env-file /opt/ABASE/env/.env.production -f deploy/hostinger/docker-compose.prod.yml up -d --force-recreate --no-deps backend celery
cd /opt/ABASE/repo && docker compose -p abase --env-file /opt/ABASE/env/.env.production -f deploy/hostinger/docker-compose.prod.yml exec -T backend python manage.py migrate --noinput
cd /opt/ABASE/repo && docker compose -p abase --env-file /opt/ABASE/env/.env.production -f deploy/hostinger/docker-compose.prod.yml exec -T backend python manage.py check
```

Se o problema for dado alterado por comando `--apply`, restaurar o backup feito
antes da aplicacao.
