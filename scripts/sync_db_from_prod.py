#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Faz dump do banco de producao via SSH/SCP,
baixa o arquivo e restaura no banco local Docker.

Uso:
    python scripts/sync_db_from_prod.py
"""

import atexit
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from tempfile import mkstemp

# -- Configuracao SSH
SSH_HOST = os.getenv("ABASE_PROD_SSH_HOST", "abasepiaui.com")
SSH_USER = os.getenv("ABASE_PROD_SSH_USER", "deploy")
SSH_KEY = os.getenv("ABASE_PROD_SSH_KEY")
SSH_KEY_CANDIDATES = [
    SSH_KEY,
    str(Path.home() / ".ssh" / "abase_deploy"),
    "/mnt/c/Users/helciovenancio/.ssh/abase_deploy",
]

# -- Banco de producao (dentro do container Docker no servidor)
PROD_CONTAINER = os.getenv("ABASE_PROD_DB_CONTAINER", "abase-mysql-prod")
PROD_DB_NAME = os.getenv("ABASE_PROD_DB_NAME", "abase_v2")
PROD_DB_USER = os.getenv("ABASE_PROD_DB_USER", "abase")

# -- Caminho remoto para salvar o dump
REMOTE_DUMP_DIR = os.getenv("ABASE_PROD_REMOTE_BACKUP_DIR", "/opt/ABASE/data/backups")
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
REMOTE_DUMP_FILE = f"{REMOTE_DUMP_DIR}/dump_prod_{TIMESTAMP}.sql.gz"

# -- Banco local (container Docker local)
LOCAL_CONTAINER = os.getenv("ABASE_LOCAL_DB_CONTAINER", "abase-v2-mysql-1")
LOCAL_DB_NAME = os.getenv("ABASE_LOCAL_DB_NAME", "abase_v2")
LOCAL_DB_USER = os.getenv("ABASE_LOCAL_DB_USER", "root")
LOCAL_DB_PASSWORD = os.getenv("ABASE_LOCAL_DB_PASSWORD", "abase")

# -- Destino local do dump
LOCAL_DUMP_DIR  = Path(__file__).parent.parent / "backups"
LOCAL_DUMP_FILE = LOCAL_DUMP_DIR / f"dump_prod_{TIMESTAMP}.sql.gz"


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def run_local(cmd, check=True):
    label = " ".join(str(c) for c in cmd[:7])
    log(f"LOCAL: {label}{'...' if len(cmd) > 7 else ''}")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and result.returncode != 0:
        print(result.stderr[-2000:], file=sys.stderr)
        sys.exit(1)
    return result


def mysql_password_args(password: str | None) -> list[str]:
    if not password:
        return []
    return [f"-p{password}"]


def resolve_ssh_key() -> str:
    for candidate in SSH_KEY_CANDIDATES:
        if not candidate:
            continue
        expanded = os.path.expanduser(candidate)
        if not os.path.exists(expanded):
            continue

        mode = os.stat(expanded).st_mode & 0o777
        if mode & 0o077:
            temp_dir = "/dev/shm" if os.path.isdir("/dev/shm") else "/tmp"
            fd, temp_path = mkstemp(prefix="abase_deploy_", dir=temp_dir)
            os.close(fd)
            with open(expanded, "rb") as src, open(temp_path, "wb") as dst:
                dst.write(src.read())
            os.chmod(temp_path, 0o600)
            atexit.register(lambda path=temp_path: os.path.exists(path) and os.remove(path))
            log(f"Usando copia temporaria protegida da chave SSH: {expanded}")
            return temp_path

        return expanded

    print(
        "Nenhuma chave SSH encontrada. Defina ABASE_PROD_SSH_KEY ou disponibilize uma das chaves padrao.",
        file=sys.stderr,
    )
    sys.exit(1)


def ssh_base_cmd(ssh_key: str) -> list[str]:
    return [
        "ssh",
        "-i",
        ssh_key,
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ConnectTimeout=20",
        f"{SSH_USER}@{SSH_HOST}",
    ]


def scp_base_cmd(ssh_key: str) -> list[str]:
    return [
        "scp",
        "-i",
        ssh_key,
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ConnectTimeout=20",
    ]


def run_ssh(ssh_key: str, remote_cmd: str, check=True):
    short = remote_cmd[:120] + ("..." if len(remote_cmd) > 120 else "")
    log(f"SSH: {short}")
    result = subprocess.run(
        ssh_base_cmd(ssh_key) + [remote_cmd],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and result.returncode != 0:
        print(result.stderr[-4000:], file=sys.stderr)
        sys.exit(1)
    return result


def main():
    LOCAL_DUMP_DIR.mkdir(parents=True, exist_ok=True)
    ssh_key = resolve_ssh_key()

    # 1. Validar acesso SSH
    log(f"Conectando em {SSH_USER}@{SSH_HOST} ...")
    out = run_ssh(ssh_key, "hostname")
    log(f"Conectado em {out.stdout.strip() or SSH_HOST}.")

    # 2. Criar diretorio de backup no servidor
    run_ssh(ssh_key, f"mkdir -p {shlex.quote(REMOTE_DUMP_DIR)}")

    # 3. Dump do banco de producao
    log(f"Gerando dump de {PROD_DB_NAME} ...")
    mysql_dump_cmd = (
        'export MYSQL_PWD="${MYSQL_PASSWORD}"; '
        f'exec mysqldump -u"${{MYSQL_USER:-{PROD_DB_USER}}}" '
        '--single-transaction --quick --routines --triggers --no-tablespaces '
        f'"${{MYSQL_DATABASE:-{PROD_DB_NAME}}}"'
    )
    dump_cmd = (
        f"docker exec {shlex.quote(PROD_CONTAINER)} sh -lc {shlex.quote(mysql_dump_cmd)} "
        f"| gzip -1 > {shlex.quote(REMOTE_DUMP_FILE)}"
    )
    dump_result = run_ssh(ssh_key, dump_cmd, check=False)
    if dump_result.returncode != 0:
        print(f"Falha no dump:\n{dump_result.stderr[-4000:]}", file=sys.stderr)
        sys.exit(1)

    # Verificar tamanho
    size_result = run_ssh(ssh_key, f"wc -c < {shlex.quote(REMOTE_DUMP_FILE)}")
    size_bytes = int(size_result.stdout.strip()) if size_result.stdout.strip().isdigit() else 0
    log(f"Dump gerado: {size_bytes / 1_048_576:.1f} MB  ({REMOTE_DUMP_FILE})")

    if size_bytes < 1024:
        print("Dump muito pequeno -- verifique credenciais ou banco.", file=sys.stderr)
        sys.exit(1)

    # 4. Baixar dump via SCP
    log(f"Baixando dump -> {LOCAL_DUMP_FILE} ...")
    run_local(
        scp_base_cmd(ssh_key) + [f"{SSH_USER}@{SSH_HOST}:{REMOTE_DUMP_FILE}", str(LOCAL_DUMP_FILE)]
    )
    local_size = LOCAL_DUMP_FILE.stat().st_size
    log(f"Download concluido: {local_size / 1_048_576:.1f} MB local.")

    # 5. Remover dump remoto
    run_ssh(ssh_key, f"rm -f {shlex.quote(REMOTE_DUMP_FILE)}")
    log("Dump remoto removido.")

    # 6. Garantir que o MySQL local esta rodando
    log("Verificando MySQL local ...")
    r = run_local(["docker", "inspect", "-f", "{{.State.Running}}", LOCAL_CONTAINER], check=False)
    if r.stdout.strip() != "true":
        log("Container local nao esta rodando, iniciando ...")
        run_local(["docker", "start", LOCAL_CONTAINER])
        time.sleep(5)

    # Aguardar MySQL ficar pronto
    log("Aguardando MySQL local ficar pronto ...")
    for attempt in range(30):
        r = run_local(
            ["docker", "exec", LOCAL_CONTAINER,
             "mysqladmin", "ping", "-h", "localhost", f"-u{LOCAL_DB_USER}"] +
            mysql_password_args(LOCAL_DB_PASSWORD),
            check=False,
        )
        if r.returncode == 0:
            break
        log(f"  aguardando... tentativa {attempt + 1}/30")
        time.sleep(2)
    else:
        print("MySQL local nao ficou pronto a tempo.", file=sys.stderr)
        sys.exit(1)
    log("MySQL local pronto.")

    # 7. Recriar banco local
    log(f"Recriando banco local '{LOCAL_DB_NAME}' ...")
    drop_create = (
        f"DROP DATABASE IF EXISTS `{LOCAL_DB_NAME}`; "
        f"CREATE DATABASE `{LOCAL_DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    )
    run_local(
        ["docker", "exec", LOCAL_CONTAINER, "mysql", f"-u{LOCAL_DB_USER}"] +
        mysql_password_args(LOCAL_DB_PASSWORD) +
        ["-e", drop_create]
    )

    # 8. Importar dump no banco local
    log(f"Importando dump em '{LOCAL_DB_NAME}' ... (pode demorar)")
    run_local(["docker", "cp", str(LOCAL_DUMP_FILE), f"{LOCAL_CONTAINER}:/tmp/restore.sql.gz"])
    run_local([
        "docker", "exec", LOCAL_CONTAINER,
        "bash", "-c",
        (
            f"gunzip -c /tmp/restore.sql.gz | mysql -u{LOCAL_DB_USER} "
            f"{('-p' + LOCAL_DB_PASSWORD + ' ') if LOCAL_DB_PASSWORD else ''}"
            f"{LOCAL_DB_NAME} && rm /tmp/restore.sql.gz"
        ),
    ])
    log("Importacao concluida.")

    # 9. Verificacao rapida
    r = run_local(
        ["docker", "exec", LOCAL_CONTAINER, "mysql", f"-u{LOCAL_DB_USER}"] +
        mysql_password_args(LOCAL_DB_PASSWORD) +
        [LOCAL_DB_NAME, "-e",
         "SELECT status, COUNT(*) as total FROM associados_associado WHERE deleted_at IS NULL GROUP BY status ORDER BY total DESC;"],
        check=False,
    )
    log(f"Verificacao associados:\n{r.stdout.strip()}")

    log(f"Sucesso! Dump salvo em: {LOCAL_DUMP_FILE}")


if __name__ == "__main__":
    main()
