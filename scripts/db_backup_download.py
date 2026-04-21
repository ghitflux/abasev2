#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ABASE v2 - Backup producao -> restore local (preserva usuarios locais)
Tambem verifica uso de disco na VPS.

Uso:
    python scripts/db_backup_download.py
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import os
import time
import subprocess
import paramiko
from pathlib import Path

# ── CONFIGURAÇÃO ─────────────────────────────────────────────────────────────

SSH_HOST     = "abasepiaui.com"
SSH_PORT     = 22
SSH_USER     = "deploy"
SSH_PASSWORD = "AbasePI2026##"
SSH_KEY_PATH = None  # tenta chave primeiro, cai para senha

MYSQL_CONTAINER = "abase-mysql-prod"
MYSQL_DATABASE  = "abase_v2"
MYSQL_USER      = "abase"
MYSQL_PASSWORD  = None   # preenchido automaticamente via inspect do container

REMOTE_TMP  = "/tmp"
DUMP_DIR    = Path(__file__).parent.parent / "backups"

# Banco local (backend/.env)
LOCAL_DB      = "abase"
LOCAL_USER    = "root"
LOCAL_PASS    = ""
LOCAL_HOST    = "127.0.0.1"
LOCAL_PORT    = "3306"

# Tabelas de usuário a preservar localmente
USER_TABLES = ["accounts_user", "accounts_userrole"]

# ─────────────────────────────────────────────────────────────────────────────


def connect_ssh() -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    kwargs = dict(hostname=SSH_HOST, port=SSH_PORT, username=SSH_USER)

    if SSH_KEY_PATH:
        kwargs["key_filename"] = os.path.expanduser(SSH_KEY_PATH)
        print(f"  Chave: {SSH_KEY_PATH}")
    elif SSH_PASSWORD:
        kwargs["password"] = SSH_PASSWORD
        print("  Autenticação por senha")

    print(f"Conectando {SSH_USER}@{SSH_HOST}:{SSH_PORT} ...")
    client.connect(**kwargs)
    print("  Conexão estabelecida.\n")
    return client


def run(client: paramiko.SSHClient, cmd: str, check=True) -> str:
    stdin, stdout, stderr = client.exec_command(cmd)
    code = stdout.channel.recv_exit_status()
    out  = stdout.read().decode().strip()
    err  = stderr.read().decode().strip()
    if check and code != 0:
        raise RuntimeError(f"Erro remoto (exit {code}):\n  {cmd}\n  {err}")
    return out


def get_mysql_password(client: paramiko.SSHClient) -> str:
    """Lê MYSQL_PASSWORD do ambiente do container no servidor."""
    out = run(
        client,
        f"docker inspect --format '{{{{.Config.Env}}}}' {MYSQL_CONTAINER}"
    )
    for part in out.strip("[]").split(" "):
        if part.startswith("MYSQL_PASSWORD="):
            return part.split("=", 1)[1]
    raise RuntimeError("Não foi possível obter MYSQL_PASSWORD do container.")


# ── ETAPAS ───────────────────────────────────────────────────────────────────

def check_disk(client: paramiko.SSHClient):
    print("=" * 60)
    print("VERIFICAÇÃO DE DISCO NA VPS")
    print("=" * 60)

    print("\n── df -h ──")
    print(run(client, "df -h"))

    print("\n── Docker disk usage ──")
    print(run(client, "docker system df"))

    print("\n── Maiores itens em /var/lib/docker ──")
    print(run(client, "du -sh /var/lib/docker/* 2>/dev/null | sort -rh | head -10", check=False))

    print("\n── Logs dos containers (tamanho) ──")
    print(run(client, r"find /var/lib/docker/containers -name '*.log' -exec du -sh {} \; 2>/dev/null | sort -rh | head -10", check=False))

    print("\n── Imagens Docker não usadas ──")
    print(run(client, "docker images --filter dangling=true --format '{{.Repository}}:{{.Tag}} {{.Size}}'", check=False))

    print("\n── Volumes Docker ──")
    print(run(client, "docker volume ls --format '{{.Name}}'", check=False))

    print()


def dump_remote(client: paramiko.SSHClient, mysql_pass: str) -> str:
    timestamp   = time.strftime("%Y%m%d_%H%M%S")
    dump_file   = f"abase_v2_{timestamp}.sql"
    remote_path = f"{REMOTE_TMP}/{dump_file}"

    print(f"[1/5] Gerando dump em {remote_path} ...")
    cmd = (
        f"docker exec {MYSQL_CONTAINER} "
        f"mysqldump -u{MYSQL_USER} -p'{mysql_pass}' "
        f"--single-transaction --routines --triggers --events "
        f"--set-gtid-purged=OFF "
        f"{MYSQL_DATABASE} > {remote_path}"
    )
    run(client, cmd)
    size = run(client, f"du -sh {remote_path}")
    print(f"  Dump gerado: {size}\n")
    return remote_path


def download_dump(client: paramiko.SSHClient, remote_path: str) -> Path:
    DUMP_DIR.mkdir(parents=True, exist_ok=True)
    local_path = DUMP_DIR / Path(remote_path).name

    print(f"[2/5] Baixando para {local_path} ...")
    sftp = client.open_sftp()
    sftp.get(remote_path, str(local_path))
    sftp.close()
    print(f"  {local_path.stat().st_size / 1024 / 1024:.1f} MB baixados.\n")
    return local_path


def cleanup_remote(client: paramiko.SSHClient, remote_path: str):
    print(f"[3/5] Removendo dump temporário do servidor ...")
    run(client, f"rm -f {remote_path}")
    print("  Removido.\n")


def mysql_local(sql: str, db: str = "", extra: str = "") -> int:
    pass_flag = f"-p{LOCAL_PASS}" if LOCAL_PASS else ""
    db_flag   = db if db else ""
    cmd = f'mysql -u{LOCAL_USER} {pass_flag} -h{LOCAL_HOST} -P{LOCAL_PORT} {db_flag} {extra} -e "{sql}"'
    return os.system(cmd)


def backup_local_users() -> Path:
    """Salva usuários locais antes do restore."""
    print("[4/5] Salvando usuários locais ...")
    DUMP_DIR.mkdir(parents=True, exist_ok=True)
    ts        = time.strftime("%Y%m%d_%H%M%S")
    out_path  = DUMP_DIR / f"local_users_backup_{ts}.sql"
    pass_flag = f"-p{LOCAL_PASS}" if LOCAL_PASS else ""
    tables    = " ".join(USER_TABLES)

    ret = os.system(
        f'mysqldump -u{LOCAL_USER} {pass_flag} -h{LOCAL_HOST} -P{LOCAL_PORT} '
        f'{LOCAL_DB} {tables} > "{out_path}" 2>NUL'
    )
    if ret != 0 or out_path.stat().st_size < 50:
        print("  Aviso: banco local vazio ou sem usuários — pulando backup de usuários.")
        out_path.unlink(missing_ok=True)
        return None

    print(f"  Usuários locais salvos em {out_path}\n")
    return out_path


def restore_local(local_path: Path, users_backup: Path):
    print(f"[5/5] Restaurando dump no banco local '{LOCAL_DB}' ...")
    pass_flag = f"-p{LOCAL_PASS}" if LOCAL_PASS else ""

    # Recriar banco
    ret = os.system(
        f'mysql -u{LOCAL_USER} {pass_flag} -h{LOCAL_HOST} -P{LOCAL_PORT} '
        f'-e "DROP DATABASE IF EXISTS {LOCAL_DB}; '
        f'CREATE DATABASE {LOCAL_DB} '
        f'CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"'
    )
    if ret != 0:
        raise RuntimeError("Falha ao recriar banco local.")

    # Importar dump de produção
    ret = os.system(
        f'mysql -u{LOCAL_USER} {pass_flag} -h{LOCAL_HOST} -P{LOCAL_PORT} '
        f'{LOCAL_DB} < "{local_path}"'
    )
    if ret != 0:
        raise RuntimeError("Falha ao importar dump de produção.")
    print("  Dump de produção importado.")

    # Restaurar usuários locais (INSERT IGNORE = não sobrescreve se já existe em prod)
    if users_backup and users_backup.exists():
        print("  Restaurando usuários locais (INSERT IGNORE — preserva produção se conflito) ...")
        # Ajustar dump para usar INSERT IGNORE
        content = users_backup.read_text(encoding="utf-8", errors="ignore")
        content = content.replace("INSERT INTO", "INSERT IGNORE INTO")
        tmp_users = DUMP_DIR / "tmp_users_ignore.sql"
        tmp_users.write_text(content, encoding="utf-8")

        ret = os.system(
            f'mysql -u{LOCAL_USER} {pass_flag} -h{LOCAL_HOST} -P{LOCAL_PORT} '
            f'{LOCAL_DB} < "{tmp_users}"'
        )
        tmp_users.unlink(missing_ok=True)
        if ret != 0:
            print("  Aviso: falha ao restaurar usuários locais.")
        else:
            print("  Usuários locais preservados.\n")
    else:
        print("  Nenhum usuário local para restaurar.\n")


# ── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  ABASE v2 -- Backup Producao -> Restore Local")
    print("=" * 60 + "\n")

    client = connect_ssh()
    try:
        # 0. Verificar disco
        check_disk(client)

        # 1-3. Dump + download + limpeza
        mysql_pass  = get_mysql_password(client)
        remote_path = dump_remote(client, mysql_pass)
        local_path  = download_dump(client, remote_path)
        cleanup_remote(client, remote_path)

    finally:
        client.close()
        print("  Conexão SSH encerrada.\n")

    # 4. Backup usuários locais
    users_backup = backup_local_users()

    # 5. Restore
    restore_local(local_path, users_backup)

    print("=" * 60)
    print(f"  Concluído!")
    print(f"  Dump salvo em:  {local_path}")
    print(f"  Banco local '{LOCAL_DB}' atualizado com dados de produção.")
    if users_backup:
        print(f"  Usuários locais preservados (backup: {users_backup})")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"\n[ERRO] {exc}", file=sys.stderr)
        sys.exit(1)
