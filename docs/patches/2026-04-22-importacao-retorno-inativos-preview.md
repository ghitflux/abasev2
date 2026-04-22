# Patch 2026-04-22: Previa da Importacao com Inativos Descontados

## Contexto

Foi validado no fluxo de importacao de arquivo retorno que um associado
`inativo` pode continuar sofrendo baixa financeira de parcela sem ser
reativado.

Isso significa que o status do associado permanece `inativo`, mas a importacao
do retorno ainda consegue:

- marcar a parcela da competencia como `descontado`;
- preencher `data_pagamento`;
- refletir o desconto no resumo financeiro.

Antes deste patch, a previa da importacao nao sinalizava esse caso de forma
explicita. O operador podia confirmar o retorno sem perceber que havia
associados inativos com desconto efetivado no arquivo.

## Diagnostico confirmado

O comportamento validado localmente foi:

- a baixa financeira ocorre em
  [backend/apps/importacao/reconciliacao.py](/mnt/d/apps/abasev2/abasev2/backend/apps/importacao/reconciliacao.py:243);
- a regularizacao do associado e interrompida quando ele esta `INATIVO` em
  [backend/apps/importacao/reconciliacao.py](/mnt/d/apps/abasev2/abasev2/backend/apps/importacao/reconciliacao.py:408).

Na pratica:

- o retorno pode afetar associado inativo financeiramente;
- o sistema nao deve reativar o associado automaticamente;
- a previa precisa mostrar esse impacto antes da confirmacao.

## Objetivo do patch

Adicionar visibilidade operacional na previa da importacao para o caso:

- `associado inativo` + `baixa_efetuada` no arquivo retorno.

O comportamento esperado apos o patch e:

- se o retorno nao trouxer esse caso, nada muda na previa;
- se houver pelo menos um caso, a previa mostra um card com quantidade e
  listagem detalhada;
- a listagem permite identificar nome, CPF, matricula, orgao e acao tomada.

## Arquivos alterados

- [backend/apps/importacao/dry_run.py](/mnt/d/apps/abasev2/abasev2/backend/apps/importacao/dry_run.py)
- [backend/apps/importacao/serializers.py](/mnt/d/apps/abasev2/abasev2/backend/apps/importacao/serializers.py)
- [backend/apps/importacao/tests/test_services.py](/mnt/d/apps/abasev2/abasev2/backend/apps/importacao/tests/test_services.py)
- [apps/web/src/components/importacao/dry-run-modal.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/components/importacao/dry-run-modal.tsx)
- [apps/web/src/components/importacao/dry-run-detail-dialog.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/components/importacao/dry-run-detail-dialog.tsx)
- [apps/web/src/app/(dashboard)/importacao/page.test.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/app/(dashboard)/importacao/page.test.tsx)
- [apps/web/src/components/importacao/dry-run-detail-dialog.test.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/components/importacao/dry-run-detail-dialog.test.tsx)
- [apps/web/src/gen/models/DryRunKpis.ts](/mnt/d/apps/abasev2/abasev2/apps/web/src/gen/models/DryRunKpis.ts)
- [apps/web/src/gen/models/DryRunItem.ts](/mnt/d/apps/abasev2/abasev2/apps/web/src/gen/models/DryRunItem.ts)

## Regra aplicada

### Backend

O `dry-run` passou a devolver:

- `desconto_em_associado_inativo` em cada item;
- `associados_inativos_com_desconto` em `kpis`.

Critero aplicado:

- marcar o item quando `resultado == baixa_efetuada` e
  `associado_status_antes == inativo`.

Isso nao muda a reconciliacao real. O patch apenas torna o impacto visivel na
previa.

### Frontend

Na previa da importacao:

- foi adicionado o card `Inativos com desconto efetuado`;
- o card abre o mesmo modal detalhado usado pelos outros grupos;
- a coluna `Acao` agora pode mostrar:
  - `Retorno descontou associado inativo`
  - `Entrara em Aptos a renovar apos confirmar`
  - `Sem acao automatica`

Tambem foi incluido aviso textual no bloco `Impacto apos confirmacao` quando a
contagem for maior que zero.

## Comportamento esperado apos deploy

### Caso 1. Arquivo retorno sem inativos descontados

Esperado:

- a previa continua abrindo normalmente;
- o card novo nao aparece;
- o restante dos KPIs segue igual.

### Caso 2. Arquivo retorno com inativos descontados

Esperado:

- a previa mostra o card `Inativos com desconto efetuado`;
- ao clicar, a tabela lista os associados afetados;
- o associado continua `inativo` apos a confirmacao;
- a parcela/competencia pode aparecer como `descontado`, porque esse e o
  comportamento real atual da reconciliacao.

## Validacao local executada

Validado em `22/04/2026` no Docker local do projeto.

### 1. Containers reiniciados e saudaveis

```bash
docker compose restart
docker compose ps
```

Resultado:

- `backend` healthy
- `frontend` up
- `mysql` healthy
- `redis` healthy
- `celery` up

### 2. Testes direcionados de backend

```bash
docker compose exec -T backend python manage.py test \
  apps.importacao.tests.test_services.ArquivoRetornoServiceTestCase.test_dry_run_sinaliza_desconto_em_associado_inativo \
  apps.importacao.tests.test_services.ArquivoRetornoServiceTestCase.test_processamento_baixa_parcela_de_inativo_sem_reativar_associado \
  --keepdb
```

Resultado:

- `test_dry_run_sinaliza_desconto_em_associado_inativo ... ok`
- `test_processamento_baixa_parcela_de_inativo_sem_reativar_associado ... ok`

### 3. Check do backend

```bash
docker compose exec -T backend python manage.py check
```

Resultado:

- `System check identified no issues (0 silenced).`

### 4. Type-check do frontend

```bash
cd apps/web
pnpm --filter @abase/web type-check
```

Resultado:

- `tsc --noEmit -p tsconfig.typecheck.json` concluido sem erro.

## Limitacao conhecida da rodada

O runner local de Jest da rota de importacao ficou preso no processo e nao
devolveu saida final confiavel nesta rodada.

Tambem existe uma falha antiga na suite completa
`apps.importacao.tests.test_services`, fora do escopo deste patch:

- `test_upload_endpoint_restringe_permissao_e_processa_fixture`

Essa falha nao invalida a regra nova documentada aqui, porque os dois testes
direcionados do caso de inativos passaram no backend.

## Sem migracao

Este patch nao adiciona migracoes e nao exige reparo de dados no banco.

## Deploy recomendado no servidor

Referencia operacional completa:

- [docs/DEPLOY_HOSTINGER_VPS_PARAMIKO.md](/mnt/d/apps/abasev2/abasev2/docs/DEPLOY_HOSTINGER_VPS_PARAMIKO.md)

Como houve alteracao em backend e frontend, o deploy recomendado inclui:

- `backend`
- `frontend`
- `celery`

### Sequencia recomendada

```bash
cd /opt/ABASE/repo
bash deploy/hostinger/scripts/backup_now.sh
git fetch origin
git checkout abaseprod
git pull --ff-only origin abaseprod
git rev-parse HEAD
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml build backend frontend celery
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml up -d backend frontend celery
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml exec -T backend python manage.py migrate --noinput
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml exec -T backend python manage.py check
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml ps
```

Observacoes:

- `migrate` foi mantido na sequencia padrao, embora este patch nao tenha nova
  migration;
- `celery` deve subir junto do backend para manter o mesmo codigo do modulo
  `importacao`.

## Validacao funcional pos-deploy

Depois do deploy, validar manualmente:

1. Abrir `/importacao`.
2. Enviar um arquivo retorno que contenha ao menos um associado inativo com
   baixa efetivada.
3. Confirmar que a previa mostra o card `Inativos com desconto efetuado`.
4. Abrir o card e conferir se a listagem exibe nome, CPF, matricula e orgao do
   associado afetado.
5. Confirmar a importacao.
6. Conferir no detalhe do associado que:
   - o status continua `inativo`;
   - a competencia do retorno foi baixada financeiramente, quando houver
     parcela local correspondente.

Se houver arquivo sem esse perfil:

1. Abrir a previa da importacao.
2. Confirmar que o card novo nao aparece.

## Logs de apoio no servidor

```bash
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml logs backend --tail=150
```

## Commit sugerido

```bash
git add \
  backend/apps/importacao/dry_run.py \
  backend/apps/importacao/serializers.py \
  backend/apps/importacao/tests/test_services.py \
  apps/web/src/components/importacao/dry-run-modal.tsx \
  apps/web/src/components/importacao/dry-run-detail-dialog.tsx \
  apps/web/src/app/\(dashboard\)/importacao/page.test.tsx \
  apps/web/src/components/importacao/dry-run-detail-dialog.test.tsx \
  apps/web/src/gen/models/DryRunKpis.ts \
  apps/web/src/gen/models/DryRunItem.ts \
  docs/patches/2026-04-22-importacao-retorno-inativos-preview.md

git commit -m "importacao: destaca inativos com desconto na previa"
git push origin HEAD:abaseprod
```
