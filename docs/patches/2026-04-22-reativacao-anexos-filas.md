# Patch 2026-04-22: Reativacao, Anexos Versionados e Remocao de Filas

## Contexto

Este patch ajusta tres regras operacionais do proximo update:

- reativacao continua criando um novo contrato, mas o ciclo real so nasce na
  efetivacao da tesouraria;
- uploads de documentos e comprovantes passam a adicionar nova versao, sem
  substituir ou apagar anexos antigos;
- remover linha de fila passa a ocultar somente a linha operacional,
  preservando associado, documentos, contratos e historico.

## Reativacao

### Regra aplicada

O endpoint `POST /api/v1/associados/{id}/reativar/` cria o novo contrato de
reativacao e envia o item para a esteira, mas nao materializa ciclo operacional
nesse momento.

Na listagem `GET /api/v1/tesouraria/contratos/`, contratos de origem
`reativacao` passam a devolver `reactivation_cycle_preview` com:

- ultima parcela descontada/liquidada do associado;
- competencia inicial sugerida;
- competencias sugeridas para o novo ciclo.

Na efetivacao `POST /api/v1/tesouraria/contratos/{id}/efetivar/`, reativacoes
exigem `competencias_ciclo`. As competencias precisam ser meses contiguos e
ter o mesmo total do prazo do contrato.

### Efeito na efetivacao

Ao efetivar uma reativacao:

- o ciclo historico anterior da ultima parcela paga e marcado como `fechado`;
- previsoes conflitantes sem evidencia financeira nas competencias escolhidas
  sao canceladas e ocultadas;
- o novo contrato recebe um ciclo `aberto`;
- o associado fica `ativo`;
- o fluxo de reativacao fica concluido na tesouraria.

Exemplo validado:

- ultima parcela paga: `2026-03-01`;
- ciclo novo confirmado: `2026-04-01`, `2026-05-01`, `2026-06-01`.

## Anexos e Comprovantes

Uploads em `POST /api/v1/associados/{id}/documentos/` agora sempre criam uma
nova linha `Documento`.

Permissoes liberadas para upload:

- `ADMIN`;
- `COORDENADOR`;
- `ANALISTA`;
- `AGENTE` responsavel pelo associado.

O mobile legado e o endpoint mobile v1 tambem passam a criar nova linha no
reupload. A versao antiga permanece ativa no historico com arquivo, datas e
metadados preservados.

O editor avancado tambem segue a regra de historico:

- `versionar_documento` cria a nova versao sem `soft_delete()` da anterior;
- `versionar_comprovante` cria a nova versao sem `soft_delete()` do anterior;
- a reversao do evento remove apenas a versao nova criada pelo evento.

Na tesouraria, novos uploads de comprovante de contrato e renovacao tambem
criam novos registros de `Comprovante`. O pagamento operacional continua
apontando para o comprovante mais recente.

## Remocao de Filas

Foi criado `POST /api/v1/esteira/{id}/remover-fila/`.

Permissoes:

- `ADMIN`;
- `COORDENADOR`;
- `ANALISTA`.

A acao:

- cancela pendencias abertas;
- registra transicao `remover_fila_operacional`;
- move o item para `concluido/rejeitado`;
- aplica `soft_delete()` apenas na linha da esteira;
- preserva associado, documentos, contrato e historico.

Na tesouraria:

- `POST /api/v1/tesouraria/contratos/{id}/excluir/` passa a usar essa remocao
  operacional;
- `POST /api/v1/tesouraria/refinanciamentos/{id}/excluir/` passa a ocultar a
  linha operacional de renovacao via `limpar_linha_operacional`.

No dashboard de analise, o analista passa a ter o botao `Remover da fila` nos
itens em analise, com confirmacao de preservacao do associado.

## Inativacao e Editor Avancado

Na tela de detalhes do associado, a acao `Inativar associado` agora exige a
escolha operacional do destino:

- `Inativo inadimplente`, gravando o associado como `inadimplente`;
- `Inativo passivel de renovacao`, gravando o associado como `apto_a_renovar`.

O endpoint `POST /api/v1/associados/{id}/inativar/` aceita `status_destino`.
Sem o campo, a API mantem compatibilidade e usa a inativacao simples anterior.

No editor avancado, parcelas salvas como `nao_descontado` dentro de um ciclo
manual permanecem no ciclo e tambem alimentam o resumo de meses nao descontados.
Quando o payload chega duplicado entre o bloco de ciclo e o bloco de inadimplencia,
o sistema preserva a linha do ciclo e usa a duplicacao apenas como resumo
financeiro, sem sumir com a parcela do cadastro do associado.

Tambem foi adicionada a reversao administrativa da inativacao no proprio modo
editor avancado:

- o detalhe do associado passa a expor `Reverter inativacao` quando existir o
  ultimo evento de inativacao ainda reversivel;
- a reversao restaura o status anterior do associado sem abrir um novo fluxo de
  reativacao;
- a reversao recompõe a linha operacional da esteira a partir do snapshot do
  evento administrativo;
- o editor avancado continua acessivel para ajustar cadastro, ciclos, esteira e
  arquivos mesmo com o associado inativo;
- a reversao usa o endpoint existente
  `POST /api/v1/admin-overrides/events/{id}/reverter/`, agora com contexto
  suficiente para restaurar associado e esteira.

## Arquivos principais alterados

- [backend/apps/associados/services.py](/mnt/d/apps/abasev2/abasev2/backend/apps/associados/services.py)
- [backend/apps/associados/serializers.py](/mnt/d/apps/abasev2/abasev2/backend/apps/associados/serializers.py)
- [backend/apps/associados/views.py](/mnt/d/apps/abasev2/abasev2/backend/apps/associados/views.py)
- [backend/apps/associados/mobile_legacy_views.py](/mnt/d/apps/abasev2/abasev2/backend/apps/associados/mobile_legacy_views.py)
- [backend/apps/associados/admin_override_service.py](/mnt/d/apps/abasev2/abasev2/backend/apps/associados/admin_override_service.py)
- [backend/apps/associados/admin_override_serializers.py](/mnt/d/apps/abasev2/abasev2/backend/apps/associados/admin_override_serializers.py)
- [backend/apps/tesouraria/services.py](/mnt/d/apps/abasev2/abasev2/backend/apps/tesouraria/services.py)
- [backend/apps/tesouraria/serializers.py](/mnt/d/apps/abasev2/abasev2/backend/apps/tesouraria/serializers.py)
- [backend/apps/tesouraria/views.py](/mnt/d/apps/abasev2/abasev2/backend/apps/tesouraria/views.py)
- [backend/apps/esteira/services.py](/mnt/d/apps/abasev2/abasev2/backend/apps/esteira/services.py)
- [backend/apps/esteira/views.py](/mnt/d/apps/abasev2/abasev2/backend/apps/esteira/views.py)
- [backend/apps/contratos/cycle_projection.py](/mnt/d/apps/abasev2/abasev2/backend/apps/contratos/cycle_projection.py)
- [backend/apps/refinanciamento/views.py](/mnt/d/apps/abasev2/abasev2/backend/apps/refinanciamento/views.py)
- [backend/apps/refinanciamento/services.py](/mnt/d/apps/abasev2/abasev2/backend/apps/refinanciamento/services.py)
- [apps/web/src/app/(dashboard)/tesouraria/page.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/app/(dashboard)/tesouraria/page.tsx)
- [apps/web/src/app/(dashboard)/analise/page.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/app/(dashboard)/analise/page.tsx)
- [apps/web/src/app/(dashboard)/associados/[id]/page.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/app/(dashboard)/associados/[id]/page.tsx)
- [apps/web/src/app/(dashboard)/associados-editar/[id]/page.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/app/(dashboard)/associados-editar/[id]/page.tsx)
- [apps/web/src/components/associados/associado-reactivation-dialog.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/components/associados/associado-reactivation-dialog.tsx)
- [apps/web/src/components/associados/associado-form.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/components/associados/associado-form.tsx)
- [apps/web/src/lib/api/types.ts](/mnt/d/apps/abasev2/abasev2/apps/web/src/lib/api/types.ts)

## Validacao executada

Validado em `22/04/2026` no Docker local.

### Backend focado

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

Validacao adicional para inativacao e editor avancado:

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
  'src/app/(dashboard)/associados/[id]/page.test.tsx' \
  --ci --forceExit
```

Resultado:

- `tsc --noEmit -p tsconfig.typecheck.json` concluido sem erro.
- `1 passed, 3 tests passed`.

## Observacao sobre suite ampla

Uma execucao ampla incluindo todo
`apps.refinanciamento.tests.test_refinanciamento_pagamentos` encontrou falhas
preexistentes/adjacentes em regras de aptidao e materializacao de renovacao
manual. Os testes focados deste patch passaram e cobrem as regras alteradas
nesta entrega.

## Sem migracao

Este patch nao adiciona migracoes e nao exige rebuild global de ciclos.
