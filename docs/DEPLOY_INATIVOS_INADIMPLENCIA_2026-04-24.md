# Deploy 2026-04-24

## Escopo deste patch

Este patch ajusta a regra operacional para associados inativos no editor
avancado e amplia o fluxo de `Tesouraria > Inadimplentes` para geracao,
quitacao e descarte manual de inadimplencia.

### Regras aplicadas

- o editor avancado volta a carregar o contrato operacional visivel do
  associado inativo, mesmo quando a inativacao anterior deixou o contrato com
  status `cancelado`;
- `save-all` volta a aceitar esse contrato visivel do inativo para materializar
  ciclos e parcelas manualmente;
- passa a ser possivel criar ciclo e parcela `nao_descontado` para associado
  inativo sem perder o status mae `inativo`;
- ao inativar, o associado permanece `inativo`; as parcelas ja existentes nao
  sao excluidas por essa correcao;
- a rota `Tesouraria > Inadimplentes` passa a exibir corretamente:
  - parcelas `nao_descontado` materializadas para associado inativo;
  - itens de arquivo retorno sem parcela vinculada para associado inativo;
- a tesouraria pode gerar inadimplencia manual para qualquer associado, em
  qualquer status, escolhendo entre:
  - registrar a linha como pendente na fila;
  - gerar e quitar diretamente com comprovante;
- ao descartar uma inadimplencia manual, a linha sai da fila e a parcela
  manual tambem deixa de existir no detalhe do associado;
- o perfil `TESOUREIRO` passa a poder executar tambem o descarte em
  `Inadimplentes`, ficando com todas as acoes da rota;
- a correcao nao exige rebuild global de ciclos.

## Arquivos alterados neste patch

- `backend/apps/associados/admin_override_service.py`
- `backend/apps/tesouraria/serializers.py`
- `backend/apps/tesouraria/services.py`
- `backend/apps/tesouraria/views.py`
- `apps/web/src/app/(dashboard)/tesouraria/baixa-manual/page.tsx`
- `backend/apps/associados/tests/test_admin_overrides.py`
- `backend/apps/associados/tests/test_permissions.py`
- `backend/apps/tesouraria/tests/test_baixa_manual.py`

## Resumo tecnico

### Editor avancado

- o carregamento do editor deixou de depender apenas de
  `associado.contratos.exclude(status=cancelado)`;
- para associado `inativo`, o editor agora usa o contrato operacional visivel
  ou, se necessario, o contrato historico operacional nao sombreado;
- o mesmo criterio foi aplicado ao `save-all`, evitando erro de contrato
  invalido quando o admin tenta criar ciclo/parcela em associado inativo.

### Inadimplentes

- foi removido o filtro que descartava item de retorno sem parcela quando o
  associado estava `inativo`;
- a listagem continua aceitando normalmente parcelas materializadas com status
  `em_aberto` ou `nao_descontado`, independentemente do status do associado.
- foi adicionada a geracao manual de inadimplencia na propria rota
  `Tesouraria > Inadimplentes`, permitindo criar a parcela para qualquer
  associado e qualquer status operacional;
- a geracao manual aceita dois fluxos:
  - criar a inadimplencia e manter em `Pendentes`;
  - criar a inadimplencia e quitar imediatamente com comprovante;
- o descarte de inadimplencia manual faz `soft delete` da parcela manual, para
  remover tanto da fila quanto do detalhe do associado;
- o descarte agora tambem esta liberado para o perfil `TESOUREIRO`.

## Validacao executada

### Testes focados aprovados

Executado no container `backend`:

```bash
docker compose exec -T backend python manage.py test \
  apps.associados.tests.test_admin_overrides.AdminOverrideApiTestCase.test_admin_editor_allows_cycle_layout_for_inactive_associado \
  apps.tesouraria.tests.test_baixa_manual.BaixaManualViewSetTestCase.test_lista_pendentes_considera_nao_descontado_do_arquivo_retorno \
  apps.tesouraria.tests.test_baixa_manual.BaixaManualViewSetTestCase.test_lista_pendentes_inclui_retorno_sem_parcela_de_associado_inativo \
  apps.tesouraria.tests.test_baixa_manual.BaixaManualViewSetTestCase.test_lista_pendentes_inclui_parcela_nao_descontada_de_associado_inativo \
  --settings=config.settings.testing --noinput
```

Resultado: `4 tests OK`

### Suite da fila de inadimplentes aprovada

```bash
docker compose exec -T backend python manage.py test \
  apps.tesouraria.tests.test_baixa_manual \
  --settings=config.settings.testing --noinput
```

Resultado: `15 tests OK`

### Validacao combinada do patch atual

```bash
docker compose exec -T backend python manage.py test \
  apps.tesouraria.tests.test_baixa_manual \
  apps.associados.tests.test_permissions \
  apps.associados.tests.test_admin_overrides.AdminOverrideApiTestCase.test_admin_editor_can_revert_inactivation_to_previous_status \
  --settings=config.settings.testing --noinput
```

Resultado: `40 tests OK`

### Type-check do frontend

```bash
pnpm --filter @abase/web type-check
```

Resultado: sem erros.

### Observacao sobre regressao pre-existente no workspace

Ao ampliar para:

```bash
docker compose exec -T backend python manage.py test \
  apps.associados.tests.test_admin_overrides \
  apps.tesouraria.tests.test_baixa_manual \
  --settings=config.settings.testing --noinput
```

`apps.tesouraria.tests.test_baixa_manual` passou, mas `apps.associados.tests.test_admin_overrides`
permaneceu com 5 falhas fora deste recorte, ligadas a regras antigas de
refinanciamento, inativacao e warnings do arquivo. Como a regra valida agora e o
produto exige que associado inativado permaneça `inativo`, esses testes antigos
devem ser tratados como legado fora do escopo deste patch.

### Higiene de diff

```bash
git diff --check
```

Resultado: sem erros.

## Checklist funcional pos-deploy

1. Abrir um associado `inativo` com contrato operacional historico.
2. Ativar `Modo editor avancado`.
3. Confirmar que o contrato aparece no board de ciclos.
4. Adicionar um novo ciclo.
5. Adicionar ou manter uma parcela `nao_descontado`.
6. Salvar pelo `save-all`.
7. Abrir `Tesouraria > Inadimplentes`.
8. Confirmar que a linha criada aparece corretamente.
9. Validar tambem um caso de item de retorno sem parcela para associado
   inativo, confirmando que a linha aparece na fila.
10. Usar `Gerar inadimplencia` para um associado `ativo` e outro `inativo`.
11. Confirmar que e possivel tanto deixar em `Pendentes` quanto `Gerar e quitar`.
12. Logar com perfil `TESOUREIRO` e confirmar `Dar Baixa` e `Descartar`.
13. Descartar uma inadimplencia manual e confirmar que ela some da fila e do
    detalhe do associado.

## Procedimento padrao de atualizacao via Paramiko

O padrao de atualizacao deste patch e via Paramiko.

### Preparacao local

```bash
python -m pip install paramiko

export ABASE_HOST="IP_OU_HOST_DO_SERVIDOR"
export ABASE_USER="USUARIO_SSH"
export ABASE_KEY="/caminho/para/chave_ssh"
export ABASE_BRANCH="abaseprod"
```

### Execucao

```bash
python - <<'PY'
import os
import sys
import paramiko

host = os.environ["ABASE_HOST"]
user = os.environ["ABASE_USER"]
key_path = os.environ["ABASE_KEY"]
branch = os.environ.get("ABASE_BRANCH", "abaseprod")

commands = [
    "cd /opt/ABASE/repo && git status --short",
    "cd /opt/ABASE/repo && git rev-parse HEAD",
    "cd /opt/ABASE/repo && bash deploy/hostinger/scripts/backup_now.sh",
    f"cd /opt/ABASE/repo && git fetch origin && git checkout {branch} && git pull --ff-only origin {branch}",
    "cd /opt/ABASE/repo && git rev-parse HEAD",
    "cd /opt/ABASE/repo && docker compose -p abase --env-file /opt/ABASE/env/.env.production -f deploy/hostinger/docker-compose.prod.yml build backend frontend celery",
    "cd /opt/ABASE/repo && docker compose -p abase --env-file /opt/ABASE/env/.env.production -f deploy/hostinger/docker-compose.prod.yml up -d backend frontend celery",
    "cd /opt/ABASE/repo && docker compose -p abase --env-file /opt/ABASE/env/.env.production -f deploy/hostinger/docker-compose.prod.yml exec -T backend python manage.py migrate",
    "cd /opt/ABASE/repo && docker compose -p abase --env-file /opt/ABASE/env/.env.production -f deploy/hostinger/docker-compose.prod.yml exec -T backend python manage.py check",
    "cd /opt/ABASE/repo && docker compose -p abase --env-file /opt/ABASE/env/.env.production -f deploy/hostinger/docker-compose.prod.yml ps",
]

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname=host, username=user, key_filename=key_path, timeout=30)

try:
    for command in commands:
        print(f"\\n$ {command}", flush=True)
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

## Regras de deploy deste patch

- nao fazer deploy com `git status --short` sujo no servidor sem validar o que
  ja esta la;
- registrar o SHA anterior antes do `git pull`;
- este patch nao adiciona migration nova, mas `migrate` continua obrigatorio no
  roteiro padrao;
- nao usar ajuste manual no servidor para completar a correcao;
- rollback deve ser feito por SHA, tambem via Paramiko.

## Rollback via Paramiko

```bash
export ABASE_PREVIOUS_SHA="SHA_ANTERIOR"

python - <<'PY'
import os
import sys
import paramiko

host = os.environ["ABASE_HOST"]
user = os.environ["ABASE_USER"]
key_path = os.environ["ABASE_KEY"]
previous_sha = os.environ["ABASE_PREVIOUS_SHA"]

commands = [
    "cd /opt/ABASE/repo && git status --short",
    f"cd /opt/ABASE/repo && git checkout {previous_sha}",
    "cd /opt/ABASE/repo && docker compose -p abase --env-file /opt/ABASE/env/.env.production -f deploy/hostinger/docker-compose.prod.yml build backend frontend celery",
    "cd /opt/ABASE/repo && docker compose -p abase --env-file /opt/ABASE/env/.env.production -f deploy/hostinger/docker-compose.prod.yml up -d backend frontend celery",
    "cd /opt/ABASE/repo && docker compose -p abase --env-file /opt/ABASE/env/.env.production -f deploy/hostinger/docker-compose.prod.yml exec -T backend python manage.py migrate",
    "cd /opt/ABASE/repo && docker compose -p abase --env-file /opt/ABASE/env/.env.production -f deploy/hostinger/docker-compose.prod.yml ps",
]

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname=host, username=user, key_filename=key_path, timeout=30)

try:
    for command in commands:
        print(f"\\n$ {command}", flush=True)
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
