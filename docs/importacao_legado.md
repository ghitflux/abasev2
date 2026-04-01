# Importação Legada

## Visão Geral

O fluxo oficial de importação do legado passou a ter 2 estágios obrigatórios:

1. `import_legacy_full`
   Importa o dump de forma fiel ao legado e valida a consistência estrutural contra o SQL.

2. `post_import_legacy_enrichment`
   Aplica a lógica canônica do web novo sobre a base importada, preservando a regra global de ciclos.

O estágio 1 continua respondendo pela pergunta "o dump foi importado 100% sem divergência?".
O estágio 2 responde pela pergunta "a base importada já está enriquecida com a lógica operacional do web novo?".

## Restauração Completa do Snapshot de 31/03/2026

Para a restauração operacional completa do snapshot legado mais recente e reimportação
dos arquivos retorno de outubro/2025 a fevereiro/2026, o fluxo oficial agora é:

```bash
./scripts/restore_legacy_snapshot.sh
```

Esse script:

- gera backup SQL do banco atual;
- gera snapshot do volume `backend_media`;
- faz staging dos 5 arquivos retorno atuais;
- limpa o banco preservando auth completo;
- importa o dump `dumps_legado/abase_banco_legado_31.03.2026.sql`;
- reaplica o estágio 2 com `anexos_legado`;
- reimporta os arquivos retorno de `2025-10` a `2026-02`;
- roda `repair_manual_return_conflicts`, `rebuild_cycle_state`,
  `audit_cycle_timeline`, `audit_return_consistency` e `audit_legacy_media_assets`.

Observação importante:

- o dump e `anexos_legado` ficam no host, então a execução operacional deve usar
  o serviço `backend-tools`, que monta o repositório em `/workspace`.

## Regra Global de Ciclos

- O tamanho do ciclo respeita `prazo_meses` do contrato: `3` ou `4`.
- Dentro do ciclo só podem existir parcelas `descontado` ou `em_previsao`.
- Competência vencida sem desconto não fica no ciclo.
- Competência vencida sem row explícito no retorno vira lacuna implícita e vai para `meses_nao_pagos`.
- Baixa manual nunca recompõe ciclo.
- Se a competência foi quitada manualmente, ela permanece na mesma seção histórica de parcelas não descontadas com status `quitada`.
- A contagem de inadimplência considera apenas parcelas ainda `nao_descontado`. Itens `quitada` continuam visíveis no histórico, mas não contam como pendência ativa.

## Regra de Precedência do Retorno

- Se uma competência já existir como baixa manual e depois entrar no arquivo retorno como `status 1 / efetivado`, com o mesmo valor, a verdade passa a ser a do retorno.
- Nessa situação, o registro deixa de ser manual e volta a ser baixa automática do arquivo retorno.
- O contexto manual dessa competência é limpo (`manual_status`, `manual_paid_at`, `manual_forma_pagamento`, `recebido_manual`, `esperado_manual` e `manual_comprovante_path`).
- Depois da conversão, os ciclos são rebuildados e os itens do retorno dessa competência são reprocessados.
- Se o retorno vier como rejeitado, ou se houver divergência de valor, a baixa manual não é convertida automaticamente.

## Ordem Obrigatória do Estágio 2

O enriquecimento precisa rodar sempre nesta ordem:

1. `sync_legacy_pagamento_manual_fields --include-refi-flags`
2. `sync_legacy_renewals`
3. `sync_legacy_initial_payments`
4. `sync_legacy_media_assets`
5. `rebuild_cycle_state`
6. `audit_cycle_timeline`

Motivo da ordem:

- As baixas manuais do legado precisam entrar antes da reconstrução.
- A atualização das parcelas vencidas fica por último, dentro do `rebuild_cycle_state`, quando o sistema já conhece:
  - quitações manuais,
  - renovações efetivadas,
  - pagamento inicial,
  - evidências importadas.

## Comandos

### Estágio 1: importação fiel ao dump

```bash
docker compose --profile tools run --rm backend-tools python manage.py import_legacy_full \
  --file /workspace/dumps_legado/abase_banco_legado_31.03.2026.sql \
  --execute
```

Verificação estrutural:

```bash
docker compose --profile tools run --rm backend-tools python manage.py verify_legacy_import \
  --file /workspace/dumps_legado/abase_banco_legado_31.03.2026.sql
```

### Estágio 2: enriquecimento canônico

Execução completa:

```bash
docker compose --profile tools run --rm backend-tools python manage.py post_import_legacy_enrichment \
  --file /workspace/dumps_legado/abase_banco_legado_31.03.2026.sql \
  --legacy-media-root /workspace/anexos_legado \
  --execute
```

Execução pontual por CPF:

```bash
docker compose --profile tools run --rm backend-tools python manage.py post_import_legacy_enrichment \
  --file /workspace/dumps_legado/abase_banco_legado_31.03.2026.sql \
  --legacy-media-root /workspace/anexos_legado \
  --cpf 22808922353 \
  --execute
```

Dry-run:

```bash
docker compose --profile tools run --rm backend-tools python manage.py post_import_legacy_enrichment \
  --file /workspace/dumps_legado/abase_banco_legado_31.03.2026.sql \
  --legacy-media-root /workspace/anexos_legado
```

Auditoria e reparo de conflitos `manual x retorno efetivado`:

```bash
docker compose --profile tools run --rm backend-tools python manage.py repair_manual_return_conflicts \
  --competencia 2026-02 \
  --execute
```

Execução pontual por CPF:

```bash
docker compose --profile tools run --rm backend-tools python manage.py repair_manual_return_conflicts \
  --competencia 2026-02 \
  --cpf 77852621368 \
  --execute
```

Execução sem mídia, quando o dump está no host e o `MEDIA_ROOT` operacional está isolado em volume Docker:

```bash
docker compose --profile tools run --rm backend-tools python manage.py post_import_legacy_enrichment \
  --file /workspace/dumps_legado/abase_banco_legado_31.03.2026.sql \
  --legacy-media-root /workspace/anexos_legado \
  --skip-media \
  --execute
```

## Relatórios

O estágio 2 gera um relatório consolidado com:

- resumo da sincronização de campos manuais;
- resumo das renovações legadas sincronizadas;
- resumo dos pagamentos iniciais sincronizados;
- resumo da mídia legada canonicalizada;
- relatório do rebuild de ciclos;
- auditoria final da timeline de ciclos.

Os arquivos ficam em `backend/media/relatorios/legacy_import/`.

## Reexecução

O estágio 2 é idempotente e pode ser reexecutado:

- globalmente, após nova importação fiel;
- por `--cpf`, para recomputação pontual;
- depois de sincronizações complementares, sem alterar a garantia do estágio 1.
