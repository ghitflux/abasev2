# Patch 2026-04-15 - Editor Avançado, Status Mãe e Importação de Retorno

## Objetivo
- Eliminar inconsistências do Editor Avançado (salvamento não refletido, `cycle_ref` inválido aceito, duplicações/rebind ambíguo).
- Padronizar status do associado como status mãe (`ativo | inativo | apto_a_renovar`).
- Ajustar fluxo de retorno/reparo para manter coerência de parcela/ciclo/associado.
- Reduzir erros de frontend no `save-all` quando houver parcelas fora do ciclo e nenhum ciclo no draft.

## Regras funcionais aplicadas
- `save-all` com `cycles=[]` e `parcelas=[]` agora falha com `400`.
- `cycle_ref` ausente/inválido em parcela agora falha com `400` estruturado.
- Sem fallback silencioso para ciclo de destino em `apply_cycle_layout_override`.
- Rebind financeiro por competência só ocorre quando a referência for única (sem ambiguidade).
- Status mãe do associado passa a ser calculado por ciclo relevante:
  - `inativo` prevalece.
  - Último ciclo apto -> associado `apto_a_renovar`.
  - Último ciclo renovado/concluído -> associado `ativo`.
- Leitura de `status`, `status_renovacao` e visual no payload passa a respeitar status mãe.
- Frontend cria ciclo âncora automático quando há parcelas fora do ciclo e zero ciclos no draft.

## Arquivos alterados

### Backend
- `backend/apps/associados/admin_override_service.py`
  - validação explícita para payload vazio no `save-all` (layout);
  - erro explícito para `cycle_ref` vazio/inválido;
  - sincronização de status mãe após operações de layout/save-all;
  - serialização de associado usando status mãe.

- `backend/apps/contratos/cycle_rebuild.py`
  - rebind por referência com mapa de candidatos;
  - só rebind quando referência é única.

- `backend/apps/contratos/cycle_projection.py`
  - adicionados:
    - `normalize_associado_mother_status`
    - `resolve_associado_mother_status`
    - `resolve_associado_status_renovacao`
    - `sync_associado_mother_status`
  - ajustes de leitura de status visual/financeiro para basear em status mãe.

- `backend/apps/associados/serializers.py`
  - `status` em list/detail agora é derivado (status mãe);
  - `status_renovacao` também derivado com base única.

- `backend/apps/contratos/views.py`
  - filtros de status visual (`ativo`/`desativado`) alinhados ao status mãe.

- `backend/apps/importacao/maristela_cycle_membership.py`
  - melhoria no reparo de março para materializar competência no ciclo quando necessário;
  - validação pós-rebuild menos rígida em cenário março;
  - sincronização de status do associado via status mãe.

- `backend/apps/importacao/reconciliacao.py`
  - remoção de escrita direta para `inadimplente` no associado;
  - sincronização do status mãe após efetivar/rejeitar/regularizar.

- `backend/apps/associados/models.py`
  - adicionado `APTO_A_RENOVAR` em `Associado.Status`.

### Frontend
- `apps/web/src/components/associados/admin-contract-editor.tsx`
  - `buildCyclesPayload` exportado;
  - fallback de ciclo âncora (`auto-fallback-cycle-1`) para evitar `cycle_ref` vazio.

- `apps/web/src/components/associados/admin-contract-editor.test.tsx`
  - novo teste para ciclo âncora automático.

### Testes backend ajustados para nova regra de status mãe
- `backend/apps/contratos/tests/test_cycle_projection.py`
  - novos cenários de status mãe apto/ativo.
- `backend/apps/importacao/tests/test_repair_maristela_cycle_membership.py`
  - expectativa de status atualizada para `apto_a_renovar` no cenário corrigido de março.
- `backend/apps/importacao/tests/test_reconciliacao.py`
  - expectativa de status atualizada para `ativo` no cenário de rejeição `S` (status mãe).

## Testes executados (foco da demanda)

### Backend
- `python manage.py test --noinput apps.associados.tests.test_admin_overrides.AdminOverrideApiTestCase.test_save_all_returns_structured_validation_error_instead_of_500`
- `python manage.py test --noinput apps.associados.tests.test_admin_overrides.AdminOverrideApiTestCase.test_save_all_returns_validation_message_for_invalid_cycle_reference`
- `python manage.py test --noinput apps.associados.tests.test_admin_overrides.AdminOverrideApiTestCase.test_admin_can_save_manual_cycle_layout_and_rebuild_keeps_it`
- `python manage.py test --noinput apps.contratos.tests.test_cycle_projection.CycleProjectionTestCase.test_associado_mother_status_is_apto_when_latest_cycle_is_apto`
- `python manage.py test --noinput apps.contratos.tests.test_cycle_projection.CycleProjectionTestCase.test_associado_mother_status_returns_to_ativo_when_latest_cycle_is_renewed`
- `python manage.py test --noinput apps.importacao.tests.test_repair_maristela_cycle_membership.RepairMaristelaCycleMembershipCommandTestCase.test_execute_moves_manual_march_back_into_cycle_and_updates_status`

### Frontend
- `pnpm --dir apps/web test -- src/components/associados/admin-contract-editor.test.tsx`

## Passos de aplicação no servidor (próximo patch)
1. Subir patch no branch de release.
2. Atualizar código no servidor.
3. Backend:
   - instalar dependências (se necessário);
   - rodar `python manage.py check`;
   - rodar testes focais listados acima.
4. Frontend:
   - instalar dependências (se necessário);
   - rodar `pnpm --dir apps/web test -- src/components/associados/admin-contract-editor.test.tsx`;
   - build.
5. Reiniciar serviços.

## Checklist de smoke test pós-deploy
- Editor avançado:
  - salvar layout com `cycle_ref` inválido deve retornar erro visível;
  - `save-all` vazio de layout deve retornar erro de validação;
  - mover parcela entre ciclos não deve duplicar competência ativa no contrato.
- Status:
  - associado com ciclo apto deve aparecer como `apto_a_renovar`;
  - associado com ciclo renovado deve voltar para `ativo`;
  - filtros `ativo/desativado` de contratos coerentes com status mãe.
- Retorno:
  - cenário março/novembro não deve quebrar materialização de ciclo;
  - atualização de parcela/ciclo/status coerente para “descontou/não descontou”.

## Observações
- Não houve migração de schema obrigatória específica deste patch (mudança de `choices` no model).
- A suíte `apps/web/src/app/(dashboard)/associados/[id]/page.test.tsx` segue instável no ambiente por Suspense/act e não foi usada como gate de release deste patch.
