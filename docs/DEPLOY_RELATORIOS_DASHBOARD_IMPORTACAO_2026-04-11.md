# Deploy — Relatórios, Dashboard, Importação e Ajuste Final da Análise

Data: `2026-04-11`
Branch de produção: `abaseprod`

## Escopo deste pacote

Este deploy consolida as correções aplicadas hoje em:

- exportação de relatórios nas rotas de dashboard operacional;
- correção do PDF com tags HTML literais no resumo do relatório;
- sincronização do diálogo de exportação com os filtros ativos da tela;
- modal expandido da rota de importação para cards de resumo;
- filtro por mensalidade no modal de `novos associados` do dashboard;
- correção final da exportação da rota `dashboard análise`, com recorte por data consistente.

## Correções funcionais principais

### 1. Dashboard análise

- a exportação deixou de depender de datas auxiliares incoerentes do item;
- o recorte do relatório agora usa `updated_at` com fallback para `created_at`;
- a coluna do relatório passa a refletir isso como `Atualizado em`;
- a serialização da API de `analise/filas` agora expõe `created_at` e `updated_at`;
- o fallback de dados do associado foi corrigido para itens sem contrato operacional resolvido.

Arquivos centrais:

- `apps/web/src/app/(dashboard)/analise/page.tsx`
- `apps/web/src/lib/api/types.ts`
- `backend/apps/esteira/serializers.py`
- `backend/apps/relatorios/services.py`

### 2. Helper global de relatórios

- a coleta paginada agora respeita o tamanho real retornado pela API, evitando relatórios truncados ou com contagem incoerente quando o backend limita `page_size`;
- a normalização de timestamps ISO considera o dia local, evitando deslocamento visual de data em exportações por dia.

Arquivos centrais:

- `apps/web/src/lib/reports.ts`
- `apps/web/src/lib/reports.test.ts`

### 3. Importação

- os cards `Quitados` e `Faltando` agora abrem tabela em modal expandido, em vez de apenas mudar a aba interna;
- o modal expandido busca a listagem completa paginada, suporta rolagem, busca e exportação;
- os cards financeiros continuam abrindo o detalhamento expandido normalmente.

Arquivo central:

- `apps/web/src/app/(dashboard)/importacao/page.tsx`

### 4. Dashboard mensal

- o modal de `novos associados` ganhou filtro por faixa de mensalidade;
- a exportação do modal respeita o recorte filtrado;
- a listagem mostra mínimo, máximo e valores disponíveis.

Arquivo central:

- `apps/web/src/app/(dashboard)/dashboard/page.tsx`

### 5. Relatórios PDF/XLSX

- correção do resumo com tags HTML escapadas indevidamente no PDF;
- inclusão de rota dedicada para `/analise`;
- exportações de análise, coordenação e tesouraria passaram a respeitar melhor os filtros ativos.

Arquivo central:

- `backend/apps/relatorios/services.py`

## Validação local executada

- `pnpm --filter @abase/web test -- --runTestsByPath 'src/lib/reports.test.ts'`
  - resultado: `2/2` testes passando;
- restart local dos containers de aplicação:
  - `backend`
  - `celery`
  - `frontend`
- status local após restart:
  - `backend` saudável;
  - `frontend` em execução;
  - `celery` em execução.

Observações:

- os testes Django completos continuam dependentes de banco disponível no ambiente;
- existe ao menos um erro de tipagem preexistente em outra área de tesouraria fora deste escopo histórico;
- este documento cobre o pacote corrigido hoje, não uma suíte completa de homologação global do sistema.

## Procedimento recomendado no servidor

### 1. Backup preventivo obrigatório

Executar no servidor:

```bash
cd /opt/ABASE/repo
bash deploy/hostinger/scripts/backup_now.sh
```

Esse script salva:

- dump do MySQL;
- `media`;
- cópia do `.env.production`;
- retenção diária, semanal e mensal.

### 2. Atualizar repositório na branch de produção

```bash
cd /opt/ABASE/repo
git fetch origin
git checkout abaseprod
git pull origin abaseprod
git log --oneline -1
```

### 3. Rebuild sem cache e restart da API e do frontend web

Comandos explícitos:

```bash
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f /opt/ABASE/repo/deploy/hostinger/docker-compose.prod.yml \
  build --no-cache backend celery frontend

docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f /opt/ABASE/repo/deploy/hostinger/docker-compose.prod.yml \
  up -d --force-recreate backend celery frontend nginx
```

Se quiser usar o script oficial do projeto, ele já faz backup + pull + build sem cache + recreate:

```bash
cd /opt/ABASE/repo
bash deploy/hostinger/scripts/deploy_prod.sh
```

### 4. Conferência pós-deploy

```bash
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f /opt/ABASE/repo/deploy/hostinger/docker-compose.prod.yml ps

docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f /opt/ABASE/repo/deploy/hostinger/docker-compose.prod.yml logs --tail=150 backend

docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f /opt/ABASE/repo/deploy/hostinger/docker-compose.prod.yml logs --tail=150 frontend
```

Checks manuais prioritários após subir:

- rota `dashboard análise`: exportar relatório do dia `10/04/2026`;
- rota `importação`: abrir modal expandido pelos cards de resumo;
- rota `dashboard`: modal de `novos associados` com filtro por mensalidade;
- rota `coordenação/refinanciamento`: exportação diária e mensal;
- rota `tesouraria`: exportação diária e mensal.

## Critério de aceite deste deploy

- backup do servidor executado antes da atualização;
- `backend`, `frontend` e `celery` reconstruídos sem cache;
- containers recriados com o código novo;
- exportação da `dashboard análise` respeitando o dia selecionado;
- PDFs sem tags HTML literais no resumo;
- modal expandido da importação abrindo corretamente.
