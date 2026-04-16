# Deploy 2026-04-16

## Escopo

Correção do editor avançado para permitir que o admin reposicione um associado na etapa de renovação escolhida mesmo quando a competência atual não o colocaria automaticamente na fila de aptos.

Também corrige o caso em que o contrato aparece apto na projeção, mas não possui a linha operacional materializada na esteira de renovação, que foi o sintoma visto no servidor com Maria de Nazaré.

## Problema corrigido

- O botão `Enviar para etapa` podia falhar com a mensagem de que a competência atual não permitia a alteração.
- Em alguns contratos, a projeção mostrava condição de apto, mas a fila operacional não era materializada corretamente.
- Quando isso acontecia, o associado não entrava na esteira de aptos no servidor.
- O frontend não deixava claro para o admin quando havia divergência entre projeção e fila operacional.

## Ajuste aplicado

### Backend

- O fluxo administrativo agora pode materializar a renovação operacional ausente antes de forçar a etapa escolhida.
- A transição administrativa não depende mais do contrato estar apto na competência atual.
- Após o envio, o rebuild preserva a etapa administrativa escolhida.
- O payload do editor passa a expor warnings específicos:
  - `renewal_queue_missing`
  - `renewal_queue_divergence`
- O save-all com competências duplicadas continua salvando e retorna warning, sem bloquear a operação.
- A projeção padrão não promove mais ciclo `fechado` para `apto_a_renovar`.

### Frontend

- Após `Enviar para etapa`, o editor exibe também os warnings retornados pelo backend, além do toast de sucesso.

## Arquivos centrais

- `backend/apps/associados/admin_override_service.py`
- `backend/apps/associados/tests/test_admin_overrides.py`
- `backend/apps/contratos/cycle_projection.py`
- `apps/web/src/app/(dashboard)/associados/[id]/page.tsx`

## Resultado esperado após o deploy

- O admin pode abrir o editor avançado do associado.
- Se houver divergência entre projeção e fila operacional, ela aparece em `warnings`.
- Ao usar `Enviar para etapa`, o sistema:
  - materializa a renovação operacional, se estiver faltando
  - move o associado para a etapa escolhida
  - ajusta a esteira para refletir a ação administrativa
- Se o destino for `Apto a renovar`, o associado deve voltar para `Análise / Aguardando` e passar a aparecer na fila de aptos.

## Caso de validação prioritário

### Maria de Nazaré

Após o deploy:

1. Abrir o editor avançado da Maria de Nazaré.
2. Confirmar se o payload mostra `renewal_queue_missing` ou `renewal_queue_divergence`.
3. Usar `Enviar para etapa` e escolher `Apto a renovar`.
4. Confirmar que a operação finaliza com sucesso.
5. Reabrir o associado e validar:
   - `refinanciamento_ativo` materializado
   - esteira em `Análise / Aguardando`
   - presença da Maria de Nazaré na lista de aptos

## Procedimento de deploy

```bash
git push abasenewv2 abaseprod

cd /opt/ABASE/repo
git pull origin abaseprod

docker compose -p abase -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  build --no-cache backend frontend

docker compose -p abase -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  up -d --force-recreate --no-deps backend celery frontend
```

## Validação obrigatória no servidor

- Abrir um associado com divergência conhecida no editor avançado.
- Confirmar que os warnings aparecem no payload do editor.
- Testar `Enviar para etapa` para `Apto a renovar`.
- Confirmar que não aparece mais o bloqueio de competência atual.
- Confirmar que o associado entra corretamente na fila de aptos.
- Confirmar que o web continua exibindo o toast de sucesso e, quando houver divergência, o toast com warnings.

## Validação executada localmente

### Backend

Executado no Docker local:

```bash
docker compose run --rm backend-tools python manage.py test --noinput \
  apps.associados.tests.test_admin_overrides.AdminOverrideApiTestCase \
  apps.contratos.tests.test_cycle_projection.CycleProjectionTestCase.test_small_value_imported_contract_override_releases_apto_for_manual_editor \
  -v 2
```

Resultado:

- `Ran 24 tests in 5.355s`
- `OK`

### Frontend

Executado no Docker local:

```bash
docker compose run --rm frontend pnpm --filter @abase/web run type-check
```

Resultado:

- type-check concluído com sucesso

## Observação operacional

Este patch corrige o comportamento do sistema para o próximo deploy. Ele não altera automaticamente os dados já materializados no servidor até que o deploy seja feito e a ação administrativa seja executada novamente no editor avançado, quando necessário.
