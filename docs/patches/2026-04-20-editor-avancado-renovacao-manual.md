# Patch 2026-04-20: Editor Avancado sem Efetivacao Indevida na Renovacao

## Contexto

Foi identificado no modulo de associado, via editor avancado, um comportamento
indevido:

- salvar edicoes comuns de ciclo/layout podia materializar automaticamente uma
  linha operacional de renovacao;
- isso populava a esteira de renovacao sem a acao explicita de `Enviar para etapa`;
- ao mesmo tempo, a transicao manual do editor precisava continuar funcionando.

O objetivo deste patch e separar claramente os dois fluxos:

- `Salvar alteracoes` no editor avancado nao deve criar fila operacional;
- `Enviar para etapa` continua sendo a unica entrada explicita para materializar
  ou reposicionar a renovacao.

## Arquivos alterados

- [backend/apps/contratos/cycle_rebuild.py](/mnt/d/apps/abasev2/abasev2/backend/apps/contratos/cycle_rebuild.py)
- [backend/apps/associados/tests/test_admin_overrides.py](/mnt/d/apps/abasev2/abasev2/backend/apps/associados/tests/test_admin_overrides.py)

## Regra aplicada

Em `rebuild_contract_cycle_state()`, contratos com
`admin_manual_layout_enabled = true` nao passam mais a criar automaticamente um
`Refinanciamento` operacional quando o layout manual deixa o ciclo elegivel para
renovacao.

A criacao automatica continua permitida apenas quando:

- o rebuild recebe `force_active_operational_status`, que e exatamente o caso da
  transicao segura do editor (`Enviar para etapa`);
- ou quando ja existe uma linha operacional ativa, caso em que ela pode ser
  preservada/atualizada.

Na pratica:

- o editor pode projetar `apto_a_renovar` e mostrar warning de fila ausente;
- a fila operacional so nasce quando o usuario confirma a transicao segura.

## Validacao local executada

Validado em `20/04/2026` no Docker local do projeto.

### 1. Check do backend no container

```bash
docker compose exec -T backend python manage.py check
```

Resultado:

- `System check identified no issues (0 silenced).`

### 2. Testes focados no container backend

```bash
docker compose exec -T -e DJANGO_SETTINGS_MODULE=config.settings.testing backend \
  python manage.py test \
  apps.associados.tests.test_admin_overrides.AdminOverrideApiTestCase.test_save_all_manual_layout_does_not_materialize_renewal_queue_on_rebuild \
  apps.associados.tests.test_admin_overrides.AdminOverrideApiTestCase.test_manual_renewal_stage_transition_materializes_queue_after_manual_layout_save \
  -v 2
```

Resultado:

- `test_save_all_manual_layout_does_not_materialize_renewal_queue_on_rebuild ... ok`
- `test_manual_renewal_stage_transition_materializes_queue_after_manual_layout_save ... ok`

### 3. Sanidade de diff

```bash
python -m py_compile \
  backend/apps/contratos/cycle_rebuild.py \
  backend/apps/associados/tests/test_admin_overrides.py

git diff --check -- \
  backend/apps/contratos/cycle_rebuild.py \
  backend/apps/associados/tests/test_admin_overrides.py
```

Resultado:

- sem erro de sintaxe;
- sem whitespace error no diff.

## Sem migracao

Este patch nao adiciona migracoes e nao exige comando corretivo de dados no banco.

## Commit sugerido

```bash
git add \
  backend/apps/contratos/cycle_rebuild.py \
  backend/apps/associados/tests/test_admin_overrides.py \
  docs/patches/2026-04-20-editor-avancado-renovacao-manual.md

git commit -m "editor-avancado: evita renovacao automatica em layout manual"
git push origin HEAD:abaseprod
```

## Deploy seguro no servidor

Referencia operacional completa:

- [docs/DEPLOY_HOSTINGER_VPS_PARAMIKO.md](/mnt/d/apps/abasev2/abasev2/docs/DEPLOY_HOSTINGER_VPS_PARAMIKO.md)

### Sequencia recomendada

No servidor:

```bash
cd /opt/ABASE/repo
bash deploy/hostinger/scripts/backup_now.sh
git fetch origin
git checkout abaseprod
git pull --ff-only origin abaseprod
git rev-parse HEAD
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml build backend celery
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml up -d backend celery
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml exec -T backend python manage.py migrate
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml exec -T backend python manage.py check
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml ps
```

Observacoes:

- `frontend` nao precisa de rebuild para este patch, porque a correcao e 100%
  backend;
- `mysql` e `redis` nao entram no deploy;
- `celery` deve subir junto com o backend para manter o mesmo codigo Python da
  imagem atual.

## Validacao funcional pos-deploy

Depois do deploy, validar manualmente:

1. Abrir `Associados > detalhe do associado > editor avancado`.
2. Editar um contrato/ciclo elegivel e salvar.
3. Confirmar que o associado nao reaparece indevidamente na esteira/fila de
   renovacao so por causa do salvamento.
4. Na mesma tela, usar `Enviar para etapa`.
5. Confirmar que a renovacao e materializada e reposicionada normalmente.

Checks de apoio no servidor:

```bash
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml logs backend --tail=120
```

Se precisar inspecionar um caso especifico no shell:

```bash
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml exec -T backend python manage.py shell
```

## Rollback curto

Se o comportamento em producao divergir do esperado:

```bash
cd /opt/ABASE/repo
git rev-parse HEAD
git checkout <SHA_ANTERIOR_VALIDADO>
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml build backend celery
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml up -d backend celery
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml exec -T backend python manage.py check
```
