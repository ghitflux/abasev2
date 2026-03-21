# Importação Legada

## Visão Geral

O fluxo oficial de importação do legado passou a ter 2 estágios obrigatórios:

1. `import_legacy_full`
   Importa o dump de forma fiel ao legado e valida a consistência estrutural contra o SQL.

2. `post_import_legacy_enrichment`
   Aplica a lógica canônica do web novo sobre a base importada, preservando a regra global de ciclos.

O estágio 1 continua respondendo pela pergunta "o dump foi importado 100% sem divergência?".
O estágio 2 responde pela pergunta "a base importada já está enriquecida com a lógica operacional do web novo?".

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
docker compose exec -T backend python manage.py import_legacy_full \
  --file dumps_legado/abase_dump_legado_21.03.2026.sql \
  --execute
```

Verificação estrutural:

```bash
docker compose exec -T backend python manage.py verify_legacy_import \
  --file dumps_legado/abase_dump_legado_21.03.2026.sql
```

### Estágio 2: enriquecimento canônico

Execução completa:

```bash
docker compose exec -T backend python manage.py post_import_legacy_enrichment \
  --file dumps_legado/abase_dump_legado_21.03.2026.sql \
  --legacy-media-root anexos_legado \
  --execute
```

Execução pontual por CPF:

```bash
docker compose exec -T backend python manage.py post_import_legacy_enrichment \
  --file dumps_legado/abase_dump_legado_21.03.2026.sql \
  --legacy-media-root anexos_legado \
  --cpf 22808922353 \
  --execute
```

Dry-run:

```bash
docker compose exec -T backend python manage.py post_import_legacy_enrichment \
  --file dumps_legado/abase_dump_legado_21.03.2026.sql \
  --legacy-media-root anexos_legado
```

Auditoria e reparo de conflitos `manual x retorno efetivado`:

```bash
docker compose exec -T backend python manage.py repair_manual_return_conflicts \
  --competencia 2026-02 \
  --execute
```

Execução pontual por CPF:

```bash
docker compose exec -T backend python manage.py repair_manual_return_conflicts \
  --competencia 2026-02 \
  --cpf 77852621368 \
  --execute
```

Execução sem mídia, quando o dump está no host e o `MEDIA_ROOT` operacional está isolado em volume Docker:

```bash
docker compose exec -T backend python manage.py post_import_legacy_enrichment \
  --file dumps_legado/abase_dump_legado_21.03.2026.sql \
  --legacy-media-root anexos_legado \
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
