# Deploy 2026-04-22

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
- `apps/web/src/components/associados/associado-reactivation-dialog.tsx`
- `apps/web/src/components/associados/associado-form.tsx`
- `apps/web/src/lib/api/types.ts`

### Documentacao e testes

- `docs/patches/2026-04-22-reativacao-anexos-filas.md`
- `docs/CHECKLIST_SESSAO_2026-04-21.md`
- `backend/apps/associados/tests/test_reactivation.py`
- `backend/apps/associados/tests/test_permissions.py`
- `backend/apps/associados/tests/test_admin_overrides.py`
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
- Salvar editor avancado com parcela `nao_descontado` mantem a competencia no
  ciclo e no resumo de meses nao descontados.

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
  --settings=config.settings.testing --noinput
```

Resultado:

- `Ran 5 tests ... OK`.

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
- Teste adicional do detalhe do associado: `1 passed, 4 tests passed`.

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

## Sem migracao

Este deploy nao adiciona migrations e nao exige rebuild global de ciclos.
