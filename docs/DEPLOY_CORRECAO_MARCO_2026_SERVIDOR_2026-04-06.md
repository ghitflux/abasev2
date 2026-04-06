# Deploy da Correção de Março/2026 no Servidor

Data de referência: 6 de abril de 2026

## Objetivo

Executar a correção de março/2026 com o fluxo certo:

1. puxar dump atualizado de produção
2. restaurar localmente
3. aplicar migrations locais
4. validar a correção sobre a base espelhada
5. só então fazer backup preventivo no servidor, rebuild sem cache, restart e apply da correção

Regras preservadas:

- não rebuildar ciclos
- não recriar ciclos
- não apagar pagamentos já existentes da competência inteira
- preservar lançamentos manuais que estão fora do arquivo retorno
- fazer o resultado oficial de março fechar exatamente no retorno:
  - `662` total
  - `182` descontados
  - `480` não descontados

## Scripts prontos

- `scripts/sync_db_from_prod.py`
  - faz dump do MySQL de produção via `ssh/scp`
  - restaura no banco local correto: `abase_v2`
  - usa fallback seguro da chave em `/mnt/c/Users/helciovenancio/.ssh/abase_deploy`
- `scripts/validar_marco_2026_local.sh`
  - sincroniza o dump de produção
  - aplica migrations locais
  - copia o TXT de março para o `MEDIA_ROOT` local
  - executa a correção de março na base espelhada
- `deploy/hostinger/scripts/deploy_correcoes_marco_2026.sh`
  - roda backup preventivo no servidor
  - faz `git fetch` + `git pull --ff-only`
  - faz rebuild sem cache de `backend`, `celery` e `frontend`
  - reinicia com `--force-recreate`
  - aplica migrations
  - roda `check`
  - executa dry-run e apply da correção de março

## Ajustes técnicos incluídos

### Sync local

O script de sync foi corrigido para:

- parar de depender de `paramiko`
- usar `ssh/scp` nativos
- restaurar no banco local certo: `abase_v2`
- aceitar a chave do Windows copiando para um arquivo temporário Linux com `0600`

### Importação/correção de março

O fluxo foi endurecido para:

- parar de reaproveitar `PagamentoMensalidade` só por CPF
- usar identidade financeira por `cpf + competência + matrícula normalizada`
- reprocessar o `ArquivoRetorno` sem apagar toda a competência
- preservar lançamentos manuais fora do arquivo
- calcular o resumo financeiro da importação só no escopo das identidades presentes no arquivo retorno da competência

Na prática, isso evita dois problemas antigos:

- colapso indevido de linhas diferentes do mesmo CPF
- poluição do resultado da importação por lançamentos manuais que não pertencem ao arquivo retorno

## Validação local feita em cima do dump de produção

Sequência executada:

```bash
python scripts/sync_db_from_prod.py
docker exec abase-v2-backend-1 bash -lc "cd /app && python manage.py migrate --noinput"
docker cp backups/Relatorio_D2102-03-2026.txt \
  abase-v2-backend-1:/app/media/arquivos_retorno/f77380907be34652919cbcc719cd4619_Relatorio_D2102-03-2026.txt
docker exec abase-v2-backend-1 bash -lc \
  "cd /app && python manage.py corrigir_importacao_retorno --competencia 2026-03 --arquivo-retorno-id 46 --apply"
```

Resultado validado localmente no dump restaurado:

- `ArquivoRetorno 46`
  - `total_registros=662`
  - `baixa_efetuada=182`
  - `nao_descontado=480`
  - `ciclo_aberto=0`
- `financeiro_after_cached`
  - `total=662`
  - `ok=182`
  - `faltando=480`
  - `esperado=156645.00`
  - `recebido=48360.00`
  - `pendente=108285.00`
- `pagamentos_before_total=641`
- `pagamentos_after_total=705`
- `pagamentos_extra_fora_do_arquivo_total=43`

Leitura correta desse resultado:

- os `64` lançamentos faltantes do retorno foram criados
- os lançamentos manuais que batiam com o retorno foram promovidos para o retorno oficial
- `43` lançamentos manuais fora do arquivo foram preservados
- o resumo oficial da importação de março passou a refletir exatamente o TXT

### Parcelas reais após a validação local

Resumo do apply local nas parcelas materializadas:

- `parcelas_elegiveis_total=390`
- `parcelas_descontado_total=121`
- `parcelas_nao_descontado_total=263`
- `parcelas_sem_match_total=6`
- `cpfs_sem_parcela_total=277`

Isso é esperado porque:

- a importação oficial fecha `662` identidades do arquivo
- as parcelas reais de março existentes na base são um subconjunto disso
- a correção não cria ciclos nem parcelas artificiais

### Smoke test obrigatório

`MARCIANITA / 05201186343` permaneceu correta na validação local:

- parcela de março encontrada
- status final: `nao_descontado`
- `data_pagamento = null`

## Como repetir a validação local com um dump novo

Se você puxar um dump mais recente do servidor, basta repetir:

```bash
bash scripts/validar_marco_2026_local.sh
```

Variáveis opcionais:

```bash
COMPETENCIA=2026-03
ARQUIVO_RETORNO_ID=46
RETURN_FILE=/mnt/d/apps/abasev2/abasev2/backups/Relatorio_D2102-03-2026.txt
```

Observação importante:

- após restaurar o dump, sempre rode as migrations locais antes da validação
- isso é obrigatório porque o dump de produção ainda pode vir sem colunas novas já existentes no código local

## Deploy no servidor

Quando a validação local com o dump mais novo estiver aprovada:

```bash
bash deploy/hostinger/scripts/deploy_correcoes_marco_2026.sh
```

Variáveis opcionais no servidor:

```bash
COMPETENCIA=2026-03
ARQUIVO_RETORNO_ID=46
REPO_DIR=/opt/ABASE/repo
ENV_FILE=/opt/ABASE/env/.env.production
COMPOSE_FILE=/opt/ABASE/repo/deploy/hostinger/docker-compose.prod.yml
```

O script faz, nessa ordem:

1. backup preventivo
2. atualização do código
3. rebuild sem cache
4. restart com `--force-recreate`
5. migrations
6. `check`
7. dry-run da correção
8. apply da correção

## Comandos manuais equivalentes no servidor

```bash
cd /opt/ABASE/repo
bash deploy/hostinger/scripts/backup_now.sh
git fetch --all --prune
git pull --ff-only
docker compose -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  build --no-cache backend celery frontend
docker compose -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  up -d --force-recreate backend celery frontend
docker compose -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  exec -T backend python manage.py migrate --noinput
docker compose -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  exec -T backend python manage.py check
docker compose -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  exec -T backend python manage.py corrigir_importacao_retorno \
  --competencia 2026-03 \
  --arquivo-retorno-id 46
docker compose -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  exec -T backend python manage.py corrigir_importacao_retorno \
  --competencia 2026-03 \
  --arquivo-retorno-id 46 \
  --apply
```

## Verificações finais esperadas no servidor

- `ArquivoRetorno 46` com:
  - `662` total
  - `182` baixa efetuada
  - `480` não descontado
  - `0` ciclo aberto
- dashboard de ciclos e tela de importação refletindo esse fechamento
- `MARCIANITA / 05201186343` aparecendo como `nao_descontado`
- inadimplência seguindo a parcela/projeção sem rebuild de ciclo

## Testes executados no código antes do runbook

```bash
docker exec abase-v2-backend-1 bash -lc \
  "cd /app && python manage.py test apps.importacao.tests.test_corrigir_importacao_retorno_command apps.importacao.tests.test_services --keepdb --noinput -v 1"
```

Resultado:

- `19` testes
- `OK`
