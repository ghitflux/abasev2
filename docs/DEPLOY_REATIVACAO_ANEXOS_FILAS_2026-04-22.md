# Deploy 2026-04-22

## Atualizacao final deste pacote

Este documento tambem cobre as correcoes finais feitas em `22/04/2026` para:

- reativacao cair na secao correta da analise;
- remocao segura de linhas duplicadas de reativacao, sem apagar a linha atual;
- reativacao aprovada pela analise chegar na tesouraria sem reabrir duplicidades
  antigas removidas da fila;
- associados com status `apto_a_renovar` aparecerem em `Aptos a renovar`;
- associados com reativacao em andamento ficarem fora de `Aptos a renovar`;
- associados ja reativados e efetivados como `ativo` poderem voltar a renovar em
  ciclos futuros.

## Escopo aplicado

### Reativacao

- Reativacao continua criando novo contrato.
- O ciclo operacional da reativacao nao e mais criado no ato da solicitacao.
- A tesouraria passa a receber `reactivation_cycle_preview` em
  `GET /api/v1/tesouraria/contratos/`.
- `POST /api/v1/tesouraria/contratos/{id}/efetivar/` passa a exigir
  `competencias_ciclo` para contratos de origem `reativacao`.
- As competencias confirmadas precisam ser meses contiguos.
- Na efetivacao:
  - o ciclo historico anterior e fechado;
  - previsoes conflitantes sem evidencia financeira sao canceladas e ocultadas;
  - o novo ciclo e criado como `aberto`;
  - o associado fica `ativo`.
- Na analise, a secao `Contratos para Reativacao` passa a ser alimentada pela
  existencia de contrato operacional de origem `reativacao` ainda pendente,
  e nao mais pela origem do contrato mais recente do associado.
- A remocao de uma reativacao da fila cancela e aplica `soft_delete()` somente
  no contrato operacional pendente daquela reativacao.
- A exclusao de duplicidades de reativacao na tesouraria tambem atua somente
  sobre a linha selecionada, preservando a reativacao mais recente/correta.
- Reativacoes removidas da fila nao reaparecem quando o associado avanca para
  tesouraria em outro fluxo.

### Aptos a renovar apos reativacao

- A fila `Aptos a renovar` passa a aceitar o status mae
  `Associado.Status.APTO_A_RENOVAR` como fonte valida para exibir a linha,
  mesmo quando a competencia automatica atual nao sustentaria a aptidao.
- A etapa manual `Apto a renovar`, enviada pelo editor avancado em
  `Enviar para etapa`, deixa de gerar o aviso amarelo `renewal_queue_divergence`
  quando ja existe etapa operacional apta.
- O bloqueio de reativacao em `Aptos a renovar` e temporario:
  - bloqueia somente reativacao em andamento;
  - considera em andamento o contrato `origem_operacional=reativacao`,
    sem `auxilio_liberado_em`, e com status diferente de
    `ativo`, `cancelado` e `encerrado`;
  - depois que a reativacao e efetivada e o associado volta para `ativo`, o
    contrato pode entrar normalmente em `Aptos a renovar` em ciclos futuros.

### Anexos e comprovantes

- Upload de documento repetido cria nova linha `Documento`.
- A versao anterior permanece ativa no historico.
- Upload de documentos liberado para:
  - `ADMIN`;
  - `COORDENADOR`;
  - `ANALISTA`;
  - `AGENTE` responsavel pelo associado.
- Reupload mobile/legado segue a mesma regra de nova versao.
- Editor avancado deixa de fazer `soft_delete()` da versao anterior em:
  - `versionar_documento`;
  - `versionar_comprovante`.
- Comprovantes de tesouraria e renovacao tambem passam a criar nova versao.

### Remocao de filas

- Criado `POST /api/v1/esteira/{id}/remover-fila/`.
- Acao liberada para `ADMIN`, `COORDENADOR` e `ANALISTA`.
- A remocao:
  - cancela pendencias abertas;
  - registra transicao `remover_fila_operacional`;
  - move o item para `concluido/rejeitado`;
  - aplica `soft_delete()` apenas na linha operacional;
  - preserva associado, documentos, contrato e historico.
- Tesouraria novos contratos/reativacoes passa a usar remocao operacional.
- Tesouraria renovacoes passa a ocultar a linha via `limpar_linha_operacional`.
- Dashboard de analise passa a exibir `Remover da fila` para analista.

### Inativacao e editor avancado

- `POST /api/v1/associados/{id}/inativar/` passa a aceitar `status_destino`.
- A tela de detalhes do associado exige confirmar o destino operacional:
  - `inativo_inadimplente`;
  - `inativo_passivel_renovacao`.
- O detalhe do associado passa a oferecer `Reverter inativacao` no modo editor
  avancado quando houver evento reversivel.
- A reversao restaura o status anterior sem abrir um novo fluxo de reativacao.
- O snapshot do evento passa a restaurar tambem a linha operacional da esteira.
- Casos antigos passam a contar com `Reverter inativacao legada`, com escolha
  manual de status de retorno, etapa e situacao da esteira.
- A reversao legada usa
  `POST /api/v1/admin-overrides/associados/{id}/reverter-inativacao-legada/`.
- O editor avancado fica liberado para admin e coordenador mesmo com o
  associado inativo.
- O editor avancado preserva parcela `nao_descontado` dentro do ciclo manual.
- A mesma competencia pode aparecer no resumo de meses nao descontados sem sumir
  da lista de parcelas do ciclo.

## Arquivos centrais

### Backend

- `backend/apps/associados/services.py`
- `backend/apps/associados/serializers.py`
- `backend/apps/associados/views.py`
- `backend/apps/associados/mobile_legacy_views.py`
- `backend/apps/associados/admin_override_service.py`
- `backend/apps/associados/admin_override_serializers.py`
- `backend/apps/associados/admin_override_views.py`
- `backend/apps/contratos/renovacao.py`
- `backend/apps/contratos/cycle_projection.py`
- `backend/apps/tesouraria/services.py`
- `backend/apps/tesouraria/serializers.py`
- `backend/apps/tesouraria/views.py`
- `backend/apps/esteira/services.py`
- `backend/apps/esteira/views.py`
- `backend/apps/refinanciamento/services.py`
- `backend/apps/refinanciamento/views.py`

### Frontend web

- `apps/web/src/app/(dashboard)/tesouraria/page.tsx`
- `apps/web/src/app/(dashboard)/tesouraria/page.test.tsx`
- `apps/web/src/app/(dashboard)/analise/page.tsx`
- `apps/web/src/app/(dashboard)/associados/[id]/page.tsx`
- `apps/web/src/app/(dashboard)/associados/[id]/page.test.tsx`
- `apps/web/src/app/(dashboard)/associados-editar/[id]/page.tsx`
- `apps/web/src/components/associados/admin-legacy-inactivation-reversal-dialog.tsx`
- `apps/web/src/components/associados/associado-reactivation-dialog.tsx`
- `apps/web/src/components/associados/associado-form.tsx`
- `apps/web/src/lib/api/types.ts`

### Documentacao e testes

- `docs/patches/2026-04-22-reativacao-anexos-filas.md`
- `docs/CHECKLIST_SESSAO_2026-04-21.md`
- `backend/apps/associados/tests/test_reactivation.py`
- `backend/apps/associados/tests/test_permissions.py`
- `backend/apps/associados/tests/test_admin_overrides.py`
- `backend/apps/contratos/tests/test_renovacao.py`
- `backend/apps/esteira/tests/test_analise.py`
- `backend/apps/tesouraria/tests/test_fluxo_completo.py`
- `backend/apps/refinanciamento/tests/test_refinanciamento_pagamentos.py`

## Procedimento de deploy no servidor

```bash
cd /opt/ABASE/repo
git pull origin abaseprod

docker compose -p abase -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  build --no-cache backend frontend

docker compose -p abase -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  up -d --force-recreate --no-deps backend celery frontend
```

## Deploy via Paramiko

Use este bloco a partir da maquina local de deploy. Ele nao contem credenciais:
preencha as variaveis de ambiente antes de executar.

Se `paramiko` nao estiver instalado na maquina local:

```bash
python -m pip install paramiko
```

```bash
export ABASE_HOST="IP_OU_HOST_DO_SERVIDOR"
export ABASE_USER="USUARIO_SSH"
export ABASE_KEY="/caminho/para/chave_ssh"
export ABASE_BRANCH="abaseprod"

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

Regras:

- nao fazer deploy se `git status --short` no servidor mostrar alteracoes nao
  esperadas;
- registrar o SHA anterior exibido por `git rev-parse HEAD` antes do `pull`;
- nao usar `git reset --hard` em producao sem decisao explicita;
- nao editar arquivo manualmente no servidor para completar deploy;
- este pacote nao possui migration nova, mas `migrate` permanece no roteiro por
  ser idempotente e padrao do deploy.

### Rollback via Paramiko

Use somente se a validacao pos-deploy falhar. Substitua `SHA_ANTERIOR_VALIDADO`
pelo SHA registrado antes do `git pull`.

```bash
export ABASE_HOST="IP_OU_HOST_DO_SERVIDOR"
export ABASE_USER="USUARIO_SSH"
export ABASE_KEY="/caminho/para/chave_ssh"
export ABASE_ROLLBACK_SHA="SHA_ANTERIOR_VALIDADO"

python - <<'PY'
import os
import sys
import paramiko

host = os.environ["ABASE_HOST"]
user = os.environ["ABASE_USER"]
key_path = os.environ["ABASE_KEY"]
rollback_sha = os.environ["ABASE_ROLLBACK_SHA"]

commands = [
    "cd /opt/ABASE/repo && git rev-parse HEAD",
    f"cd /opt/ABASE/repo && git fetch origin && git checkout {rollback_sha}",
    "cd /opt/ABASE/repo && docker compose -p abase --env-file /opt/ABASE/env/.env.production -f deploy/hostinger/docker-compose.prod.yml build backend frontend celery",
    "cd /opt/ABASE/repo && docker compose -p abase --env-file /opt/ABASE/env/.env.production -f deploy/hostinger/docker-compose.prod.yml up -d backend frontend celery",
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

## Validacao obrigatoria apos deploy

### Backend

```bash
docker compose -p abase -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  exec -T backend python manage.py check
```

Validar manualmente:

- `POST /api/v1/associados/{id}/reativar/` cria contrato de reativacao sem
  ciclo.
- `GET /api/v1/tesouraria/contratos/?pagamento=pendente&origem_operacional=reativacao`
  devolve `reactivation_cycle_preview`.
- `POST /api/v1/tesouraria/contratos/{id}/efetivar/` com
  `competencias_ciclo` cria ciclo aberto e deixa associado `ativo`.
- `POST /api/v1/associados/{id}/documentos/` com mesmo tipo cria nova linha e
  preserva a anterior.
- `POST /api/v1/esteira/{id}/remover-fila/` remove a linha da fila sem excluir
  associado.
- `POST /api/v1/associados/{id}/inativar/` com `status_destino` grava o destino
  operacional escolhido.
- `POST /api/v1/admin-overrides/events/{id}/reverter/` restaura o associado
  para o status anterior da inativacao e recompõe a esteira sem abrir
  reativacao.
- `POST /api/v1/admin-overrides/associados/{id}/reverter-inativacao-legada/`
  permite reabrir casos antigos sem snapshot, com parametros operacionais
  informados manualmente.
- Salvar editor avancado com parcela `nao_descontado` mantem a competencia no
  ciclo e no resumo de meses nao descontados.
- Em `/analise`, a linha de uma reativacao pendente aparece na secao
  `Contratos para Reativacao`, nao apenas em `Ver todos`.
- Ao remover duplicidades de reativacao antigas na tesouraria, a linha correta
  mais recente do mesmo associado permanece visivel.
- Em `/renovacao-ciclos?status=apto_a_renovar`, associado com status mae
  `apto_a_renovar` aparece em `Aptos a renovar` quando nao existe reativacao
  em andamento.
- Associado com reativacao em andamento nao aparece em `Aptos a renovar`.
- Associado ja reativado e efetivado como `ativo` pode aparecer em
  `Aptos a renovar` em ciclo futuro.
- No editor avancado, apos usar `Enviar para etapa` com `Apto a renovar`, nao
  deve aparecer o aviso amarelo `renewal_queue_divergence` para etapa apta
  ja materializada.

### Frontend

Validar manualmente:

- Tesouraria mostra dialogo de confirmacao das parcelas na efetivacao de
  reativacao.
- Analise mostra `Remover da fila` para analista em itens da etapa de analise.
- Formulario e modal de reativacao usam texto de nova versao, sem promessa de
  substituicao do anexo antigo.
- Detalhe do associado mostra escolha obrigatoria entre inativo inadimplente e
  inativo passivel de renovacao antes de confirmar a inativacao.
- Modo editor avancado no detalhe do associado mostra `Reverter inativacao`
  quando houver evento elegivel e o botao volta o associado ao status anterior.
- Quando nao houver evento elegivel, o modo editor avancado mostra
  `Reverter inativacao legada` para casos antigos.
- A rota `/associados-editar/:id?admin=1` continua acessivel para ajuste
  administrativo mesmo com o associado inativo.

## Validacao local executada antes do deploy

### Testes focados de backend

```bash
docker compose exec -T backend python manage.py test \
  apps.associados.tests.test_reactivation.AssociadoReactivationTestCase \
  apps.associados.tests.test_permissions.AssociadoPermissionsTestCase.test_upload_do_mesmo_tipo_adiciona_nova_versao_sem_substituir \
  apps.associados.tests.test_permissions.AssociadoPermissionsTestCase.test_analista_pode_enviar_nova_versao_de_documento \
  apps.associados.tests.test_permissions.AssociadoPermissionsTestCase.test_coordenador_nao_pode_editar_associado_mas_pode_enviar_documentos \
  apps.esteira.tests.test_analise.AnaliseViewSetTestCase.test_remover_fila_preserva_associado_documentos_e_historico \
  apps.tesouraria.tests.test_fluxo_completo.TestFluxoCompleto.test_coordenador_pode_excluir_contrato_operacional_preservando_historico \
  apps.refinanciamento.tests.test_refinanciamento_pagamentos.RefinanciamentoPagamentosTestCase.test_coordenador_pode_remover_renovacao_da_fila_tesouraria \
  apps.refinanciamento.tests.test_refinanciamento_pagamentos.RefinanciamentoPagamentosTestCase.test_coordenacao_pode_substituir_termo_agente_na_tesouraria \
  --settings=config.settings.testing --noinput
```

Resultado:

- `Ran 13 tests ... OK`.

### Testes focados adicionais de inativacao/editor

```bash
docker compose exec -T backend python manage.py test \
  apps.associados.tests.test_permissions.AssociadoPermissionsTestCase.test_coordenador_pode_inativar_associado \
  apps.associados.tests.test_permissions.AssociadoPermissionsTestCase.test_coordenador_pode_inativar_associado_como_inadimplente \
  apps.associados.tests.test_permissions.AssociadoPermissionsTestCase.test_coordenador_pode_inativar_associado_como_passivel_de_renovacao \
  apps.associados.tests.test_admin_overrides.AdminOverrideApiTestCase.test_save_all_keeps_nao_descontado_inside_cycle_and_unpaid_summary \
  apps.associados.tests.test_admin_overrides.AdminOverrideApiTestCase.test_admin_editor_can_revert_inactivation_to_previous_status \
  apps.associados.tests.test_admin_overrides.AdminOverrideApiTestCase.test_admin_editor_can_assist_legacy_inactivation_reversal \
  --settings=config.settings.testing --noinput
```

Resultado:

- `Ran 6 tests ... OK`.

### Testes focados adicionais de reativacao, aptos e duplicidades

```bash
docker compose exec -T backend python manage.py test \
  apps.contratos.tests.test_renovacao.RenovacaoCicloViewSetTestCase.test_listagem_apta_inclui_status_mae_apto_mesmo_sem_linha_operacional \
  apps.contratos.tests.test_renovacao.RenovacaoCicloViewSetTestCase.test_listagem_apta_exclui_associado_com_reativacao_em_andamento \
  apps.contratos.tests.test_renovacao.RenovacaoCicloViewSetTestCase.test_listagem_apta_inclui_reativado_ativo_em_ciclo_futuro \
  apps.associados.tests.test_admin_overrides.AdminOverrideApiTestCase.test_admin_can_force_contract_back_to_apto_even_without_current_competencia_match \
  --settings=config.settings.testing --noinput
```

Resultado:

- `Ran 4 tests ... OK`.

```bash
docker compose exec -T backend python manage.py test \
  apps.associados.tests.test_reactivation \
  --settings=config.settings.testing --noinput
```

Resultado:

- `Ran 7 tests ... OK`.

```bash
docker compose exec -T backend python manage.py test \
  apps.tesouraria.tests.test_fluxo_completo.TestFluxoCompleto.test_remover_reativacao_antiga_nao_remove_reativacao_atual_da_tesouraria \
  apps.tesouraria.tests.test_fluxo_completo.TestFluxoCompleto.test_contrato_removido_da_fila_some_da_lista_cancelados_tesouraria \
  --settings=config.settings.testing --noinput
```

Resultado:

- `Ran 2 tests ... OK`.

### Frontend

```bash
pnpm --filter @abase/web type-check
./node_modules/.bin/jest --runTestsByPath \
  'src/app/(dashboard)/tesouraria/page.test.tsx' \
  'src/app/(dashboard)/associados/[id]/page.test.tsx' \
  --ci --forceExit
```

Resultado:

- Type-check concluido sem erro.
- `2 passed, 10 tests passed`.
- Teste adicional do detalhe do associado: `1 passed, 5 tests passed`.

### Checks gerais

```bash
docker compose exec -T backend python manage.py check --settings=config.settings.testing
git diff --check
```

Resultado:

- `System check identified no issues (0 silenced).`
- `git diff --check` sem saida.

## Reinicio local desta rodada

Executado apos a documentacao de deploy:

```bash
docker compose restart
docker compose ps
docker compose exec -T backend python manage.py check --settings=config.settings.testing
```

Resultado obtido em `22/04/2026`:

- `backend` healthy;
- `mysql` healthy;
- `redis` healthy;
- `frontend` up;
- `celery` up;
- `manage.py check` sem erros.

Smokes HTTP locais:

```bash
curl -fsS -o /tmp/abase-health.txt -w '%{http_code}\n' http://localhost:8000/api/v1/health/
curl -fsS -o /tmp/abase-frontend.txt -w '%{http_code}\n' http://localhost:3000/
```

Resultado:

- Backend health: `200`, payload `{"status": "ok", "service": "abase-backend"}`.
- Frontend: `307` redirecionando para `/login?next=%2F`, comportamento esperado para rota raiz sem sessao.

## Observacao sobre suite ampla

Uma execucao ampla incluindo todo
`apps.refinanciamento.tests.test_refinanciamento_pagamentos` acusou falhas
preexistentes/adjacentes em regras de aptidao/materializacao de renovacao
manual. Os testes focados deste deploy passaram e cobrem as regras alteradas.

Em nova execucao feita durante este fechamento, a suite completa
`apps.contratos.tests.test_renovacao` ainda apresentou 5 falhas adjacentes em
resumo/importacao/competencia. Elas nao pertencem ao recorte de reativacao,
remocao de duplicidades e aptos tratado neste deploy, mas devem permanecer
visiveis para uma sessao futura.

## Sem migracao

Este deploy nao adiciona migrations e nao exige rebuild global de ciclos.
