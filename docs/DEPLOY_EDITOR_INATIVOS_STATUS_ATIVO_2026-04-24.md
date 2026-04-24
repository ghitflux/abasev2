# Deploy 2026-04-24 - editor avancado, inativos e status Ativo

## Objetivo

Subir para o servidor o pacote de correcao que ajusta:

- visualizacao de ciclos e parcelas antigas de associados inativos no editor
  avancado;
- persistencia do status `ativo` no editor avancado, removendo o associado da
  esteira de `Aptos a renovar` quando a edicao administrativa define o status
  como `Ativo`;
- remocao de linha operacional no `Dashboard > Analise`, sem cancelar
  associado, contrato ou historico;
- correcao e validacao do associado `FRANCISCO CRISOSTOMO BATISTA`,
  CPF `21819424391`, que deve permanecer `ativo` e fora da esteira de
  renovacao.

Nao ha migration neste pacote. Nao executar rebuild global de ciclos.

## Arquivos do pacote

### Backend

- `backend/apps/associados/admin_override_service.py`
- `backend/apps/associados/tests/test_admin_overrides.py`
- `backend/apps/contratos/cycle_projection.py`
- `backend/apps/contratos/cycle_rebuild.py`
- `backend/apps/esteira/services.py`
- `backend/apps/esteira/views.py`
- `backend/apps/esteira/tests/test_analise.py`

### Frontend

- `apps/web/src/app/(dashboard)/analise/page.tsx`

## Regras funcionais cobertas

### Associado inativo no editor avancado

- O editor avancado deve exibir contratos/ciclos historicos do associado mesmo
  quando o associado estiver `inativo`.
- Ciclos manuais ja existentes, inclusive ciclos vazios, nao podem sumir ao
  reabrir o editor.
- Parcelas inadimplentes ou fora do ciclo devem continuar aparecendo no payload
  do editor.
- O `save-all` deve aceitar criacao e exclusao de parcelas dentro ou fora de
  ciclo, descontadas ou nao, sem perder o layout manual salvo pelo admin.

### Status Ativo pelo editor avancado

- Quando o admin/coordenador muda o status do associado para `Ativo`, o backend
  deve salvar o status mae como `ativo`.
- Se havia uma fila operacional ativa de renovacao, ela deve ser revertida de
  forma segura.
- Se o associado estava aparecendo em `Aptos a renovar` apenas por projecao, o
  backend deve materializar a transicao minima e reverter, criando o marcador
  necessario para que a projecao deixe de retornar a linha.
- A correcao nao pode efetivar renovacao, nao pode cancelar associado e nao
  pode apagar contrato.

### Remover da fila na dashboard analise

- `ADMIN`, `COORDENADOR` e `ANALISTA` podem remover uma linha operacional da
  fila de analise.
- A acao remove somente a linha selecionada da esteira operacional do analista.
- Nao cancela associado, nao cancela contrato e nao apaga documentos ou
  historico.

## Validacao local ja executada

### Backend

```bash
docker exec abase-v2-backend-1 python -m py_compile \
  apps/associados/admin_override_service.py \
  apps/associados/tests/test_admin_overrides.py \
  apps/contratos/cycle_projection.py \
  apps/contratos/cycle_rebuild.py \
  apps/esteira/services.py \
  apps/esteira/views.py \
  apps/esteira/tests/test_analise.py
```

Resultado: sem erro de compilacao.

```bash
docker exec abase-v2-backend-1 python manage.py test \
  apps.esteira.tests.test_analise \
  --settings=config.settings.testing --noinput
```

Resultado: `25 tests OK`.

```bash
docker exec abase-v2-backend-1 python manage.py test \
  apps.tesouraria.tests.test_fluxo_completo.TestFluxoCompleto.test_coordenador_pode_excluir_contrato_operacional_preservando_historico \
  apps.tesouraria.tests.test_fluxo_completo.TestFluxoCompleto.test_remover_reativacao_antiga_nao_remove_reativacao_atual_da_tesouraria \
  --settings=config.settings.testing --noinput
```

Resultado: aprovado.

```bash
docker exec abase-v2-backend-1 python manage.py test \
  apps.associados.tests.test_admin_overrides.AdminOverrideApiTestCase.test_editor_payload_keeps_empty_manual_cycle_visible_for_inactive_contract \
  apps.associados.tests.test_admin_overrides.AdminOverrideApiTestCase.test_admin_save_all_preserves_unpaid_rows_when_manual_layout_rebuilds \
  apps.associados.tests.test_admin_overrides.AdminOverrideApiTestCase.test_associado_core_override_active_reverts_active_renewal_queue \
  apps.associados.tests.test_admin_overrides.AdminOverrideApiTestCase.test_associado_core_override_active_blocks_projection_only_apt_queue \
  apps.associados.tests.test_admin_overrides.AdminOverrideApiTestCase.test_admin_can_revert_stale_renewal_and_keep_associado_active \
  --settings=config.settings.testing --noinput
```

Resultado: aprovado.

### Frontend

```bash
docker compose run --rm frontend pnpm --filter @abase/web type-check
```

Resultado: sem erro.

### Observacao sobre teste legado

Ao executar a suite completa de `apps.associados.tests.test_admin_overrides`,
existe uma falha ja observada fora deste recorte:

```text
test_refinanciamento_core_override_syncs_associado_status_after_desativacao
```

A falha ocorre antes das novas regras deste pacote, no retorno inicial de
`sync_associado_mother_status(self.associado)`. Os testes novos e os testes de
regressao diretamente ligados ao pacote passam isoladamente.

## Deploy via Paramiko

Execute a partir da maquina local de deploy. O bloco nao contem credenciais.

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

Se `git status --short` retornar alteracoes locais no servidor, interrompa o
deploy e salve o diff antes de atualizar.

## Validacao no servidor

Todos os comandos abaixo devem ser executados em `/opt/ABASE/repo`.

```bash
COMPOSE="docker compose -p abase --env-file /opt/ABASE/env/.env.production -f deploy/hostinger/docker-compose.prod.yml"
```

### Sanidade dos containers

```bash
$COMPOSE ps
$COMPOSE exec -T backend python manage.py check
```

### Francisco Crisostomo deve ficar Ativo e fora de Aptos

Validacao sem alterar dados:

```bash
$COMPOSE exec -T backend python manage.py shell <<'PY'
from apps.associados.models import Associado
from apps.contratos.cycle_projection import (
    build_contract_cycle_projection,
    invalidate_operational_apt_queue_cache,
    resolve_associado_mother_status,
)
from apps.contratos.renovacao import RenovacaoCicloService, parse_competencia_query
from apps.refinanciamento.models import Refinanciamento

def digits(value):
    return "".join(ch for ch in str(value or "") if ch.isdigit())

def get_associado_by_cpf(cpf):
    formatted = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    associado = Associado.objects.filter(cpf_cnpj__in=[cpf, formatted]).first()
    if associado is None:
        raise RuntimeError(f"Associado nao encontrado para CPF {cpf}.")
    return associado

cpf = "21819424391"
invalidate_operational_apt_queue_cache()
associado = get_associado_by_cpf(cpf)
contratos = list(associado.contratos.filter(deleted_at__isnull=True).order_by("id"))
aptos = [
    row for row in RenovacaoCicloService.listar_detalhes(
        competencia=parse_competencia_query(None),
        status=Refinanciamento.Status.APTO_A_RENOVAR,
    )
    if digits(row.get("cpf_cnpj")) == cpf
]

print("associado", associado.id, associado.nome_completo, associado.status)
print("status_mae", resolve_associado_mother_status(associado))
print("contratos", [(c.id, c.codigo, c.status, build_contract_cycle_projection(c)["status_renovacao"]) for c in contratos])
print("refis_ativos", list(Refinanciamento.objects.filter(
    associado=associado,
    deleted_at__isnull=True,
).exclude(status__in=[
    Refinanciamento.Status.REVERTIDO,
    Refinanciamento.Status.DESATIVADO,
    Refinanciamento.Status.REJEITADO,
]).values_list("id", "status", "executado_em", "data_ativacao_ciclo", "ciclo_destino_id")))
print("linhas_aptos", len(aptos))
PY
```

Resultado esperado:

- `associado ... ativo`;
- `status_mae ativo`;
- `refis_ativos []` ou somente refinanciamentos historicos efetivados que nao
  representem fila operacional aberta;
- `linhas_aptos 0`.

Correcao idempotente, se o Francisco ainda aparecer na esteira apos o deploy:

```bash
$COMPOSE exec -T backend python manage.py shell <<'PY'
from django.contrib.auth import get_user_model

from apps.associados.admin_override_service import AdminOverrideService
from apps.associados.models import Associado
from apps.contratos.cycle_projection import invalidate_operational_apt_queue_cache
from apps.refinanciamento.models import Refinanciamento

def get_associado_by_cpf(cpf):
    formatted = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    associado = Associado.objects.filter(cpf_cnpj__in=[cpf, formatted]).first()
    if associado is None:
        raise RuntimeError(f"Associado nao encontrado para CPF {cpf}.")
    return associado

cpf = "21819424391"
User = get_user_model()
user = User.objects.filter(is_superuser=True, is_active=True).order_by("id").first()
if user is None:
    raise RuntimeError("Nao ha superusuario ativo para registrar a correcao administrativa.")

associado = get_associado_by_cpf(cpf)
print("before", associado.id, associado.nome_completo, associado.status)

AdminOverrideService.apply_associado_core_override(
    associado=associado,
    payload={
        "status": Associado.Status.ATIVO,
        "motivo": "Correcao deploy 2026-04-24: manter ativo fora da esteira de renovacao.",
    },
    user=user,
)

invalidate_operational_apt_queue_cache()
associado.refresh_from_db()
print("after", associado.id, associado.nome_completo, associado.status)
print("refis_abertos", list(Refinanciamento.objects.filter(
    associado=associado,
    deleted_at__isnull=True,
    executado_em__isnull=True,
    data_ativacao_ciclo__isnull=True,
    ciclo_destino__isnull=True,
).exclude(status__in=[
    Refinanciamento.Status.REVERTIDO,
    Refinanciamento.Status.DESATIVADO,
    Refinanciamento.Status.REJEITADO,
]).values_list("id", "status")))
PY
```

Depois de corrigir, rode novamente a validacao anterior e confirme
`linhas_aptos 0`.

### Inativos devem exibir ciclos antigos no editor avancado

Validacao especifica usando o associado de referencia Wilson Ferreira,
CPF `06319990350`:

```bash
$COMPOSE exec -T backend python manage.py shell <<'PY'
from apps.associados.admin_override_service import AdminOverrideService
from apps.associados.models import Associado

def get_associado_by_cpf(cpf):
    formatted = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    associado = Associado.objects.filter(cpf_cnpj__in=[cpf, formatted]).first()
    if associado is None:
        raise RuntimeError(f"Associado nao encontrado para CPF {cpf}.")
    return associado

cpf = "06319990350"
associado = get_associado_by_cpf(cpf)
payload = AdminOverrideService.build_associado_editor_payload(associado)

print("associado", associado.id, associado.nome_completo, associado.status)
print("contratos_payload", len(payload["contratos"]))
for contrato in payload["contratos"]:
    ciclos = contrato["ciclos"]
    unpaid = contrato["meses_nao_pagos"]
    movimentos = contrato["movimentos_financeiros_avulsos"]
    print(
        "contrato",
        contrato["id"],
        contrato["codigo"],
        "status",
        contrato["status"],
        "ciclos",
        len(ciclos),
        "meses_nao_pagos",
        len(unpaid),
        "movimentos",
        len(movimentos),
    )
    print("ciclos_resumo", [
        (ciclo["id"], ciclo["numero"], ciclo["status"], len(ciclo["parcelas"]))
        for ciclo in ciclos
    ])
PY
```

Resultado esperado:

- o payload deve conter pelo menos um contrato visivel;
- ciclos antigos materializados devem aparecer mesmo com associado `inativo`;
- ciclos manuais vazios devem aparecer com `parcelas 0`;
- parcelas inadimplentes devem aparecer em `meses_nao_pagos` ou no ciclo correto,
  conforme o layout salvo.

Auditoria amostral para demais inativos:

```bash
$COMPOSE exec -T backend python manage.py shell <<'PY'
from apps.associados.admin_override_service import AdminOverrideService
from apps.associados.models import Associado

qs = (
    Associado.objects
    .filter(status=Associado.Status.INATIVO, contratos__isnull=False)
    .distinct()
    .order_by("nome_completo")[:20]
)

for associado in qs:
    payload = AdminOverrideService.build_associado_editor_payload(associado)
    contratos = payload["contratos"]
    ciclos = sum(len(contrato["ciclos"]) for contrato in contratos)
    parcelas = sum(
        len(ciclo["parcelas"])
        for contrato in contratos
        for ciclo in contrato["ciclos"]
    )
    unpaid = sum(len(contrato["meses_nao_pagos"]) for contrato in contratos)
    print(
        associado.id,
        associado.cpf_cnpj,
        associado.nome_completo,
        "contratos",
        len(contratos),
        "ciclos",
        ciclos,
        "parcelas_ciclo",
        parcelas,
        "meses_nao_pagos",
        unpaid,
    )
PY
```

Resultado esperado: associados inativos com historico operacional devem retornar
contratos/ciclos/parcelas no payload do editor avancado, sem erro.

### Remover da fila na dashboard analise

Validacao funcional pela interface:

1. Entrar como `ADMIN`, `COORDENADOR` ou `ANALISTA`.
2. Abrir `Dashboard > Analise`.
3. Selecionar uma linha operacional elegivel.
4. Clicar em `Remover da fila`.
5. Confirmar que a linha saiu da fila de analise.
6. Abrir o associado removido e confirmar que:
   - o cadastro nao foi cancelado;
   - o contrato nao foi apagado;
   - documentos e historico continuam visiveis.

## Checklist final pos-deploy

- [ ] `backend`, `frontend` e `celery` estao `running`/saudaveis.
- [ ] `python manage.py check` passou no backend do servidor.
- [ ] Francisco Crisostomo Batista esta `ativo`.
- [ ] CPF `21819424391` retorna `linhas_aptos 0`.
- [ ] Wilson Ferreira CPF `06319990350` abre no editor avancado com ciclos
  antigos visiveis.
- [ ] Amostra de associados inativos retorna payload de editor sem erro.
- [ ] Remover da fila na dashboard analise remove somente a linha operacional.

## Rollback

Use rollback somente se o deploy quebrar fluxo operacional. Substitua
`SHA_ANTERIOR_VALIDADO` pelo commit anterior validado no servidor.

```bash
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

Variavel necessaria para rollback:

```bash
export ABASE_ROLLBACK_SHA="SHA_ANTERIOR_VALIDADO"
```
