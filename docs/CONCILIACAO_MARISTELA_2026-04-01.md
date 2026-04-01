# Conciliação Maristela 2026-04-01

Fonte de verdade utilizada: `anexos_legado/Conciliacao/planilha_manual_maristela.xlsx`

Competências conciliadas:
- `2025-10`
- `2025-12`
- `2026-01`
- `2026-02`
- `2026-03`

Regras aplicadas:
- match automático por `CPF`
- fallback por `matrícula`
- `novembro/2025` ignorado
- sem criação de associados ou contratos novos

## Execução aplicada

Relatório principal:
- [execute_summary.json](/mnt/d/apps/abasev2/abasev2/backups/maristela_sheet_20260401T152454_execute/execute_summary.json)

Arquivos gerados:
- [correcoes_aplicadas.csv](/mnt/d/apps/abasev2/abasev2/backups/maristela_sheet_20260401T152454_execute/correcoes_aplicadas.csv)
- [correcoes_aplicadas.json](/mnt/d/apps/abasev2/abasev2/backups/maristela_sheet_20260401T152454_execute/correcoes_aplicadas.json)
- [planilha_sem_match.csv](/mnt/d/apps/abasev2/abasev2/backups/maristela_sheet_20260401T152454_execute/planilha_sem_match.csv)
- [planilha_sem_match.json](/mnt/d/apps/abasev2/abasev2/backups/maristela_sheet_20260401T152454_execute/planilha_sem_match.json)
- [excecoes_conciliacao.csv](/mnt/d/apps/abasev2/abasev2/backups/maristela_sheet_20260401T152454_execute/excecoes_conciliacao.csv)
- [excecoes_conciliacao.json](/mnt/d/apps/abasev2/abasev2/backups/maristela_sheet_20260401T152454_execute/excecoes_conciliacao.json)
- [sistema_fora_da_planilha.csv](/mnt/d/apps/abasev2/abasev2/backups/maristela_sheet_20260401T152454_execute/sistema_fora_da_planilha.csv)
- [sistema_fora_da_planilha.json](/mnt/d/apps/abasev2/abasev2/backups/maristela_sheet_20260401T152454_execute/sistema_fora_da_planilha.json)
- [sistema_fora_da_planilha_priorizados.csv](/mnt/d/apps/abasev2/abasev2/backups/maristela_sheet_20260401T152454_execute/sistema_fora_da_planilha_priorizados.csv)
- [sistema_fora_da_planilha_priorizados.json](/mnt/d/apps/abasev2/abasev2/backups/maristela_sheet_20260401T152454_execute/sistema_fora_da_planilha_priorizados.json)

Resumo da execução:
- `647` linhas lidas da planilha
- `573` associados casados unicamente
- `3208` correções aplicadas
- `570` contratos rebuildados
- `74` linhas da planilha sem match único
- `472` exceções de conciliação

Distribuição das correções aplicadas:
- `1408` ajustes em `parcela`
- `352` registros de `baixa_manual`
- `459` ajustes/criações em `pagamento_mensalidade`
- `419` ajustes em `associado`
- `570` rebuilds de `contrato`

## Verificação pós-execução

Relatório de verificação:
- [dry_run_summary.json](/mnt/d/apps/abasev2/abasev2/backups/maristela_sheet_20260401T152454_verify3/dry_run_summary.json)

Resultado:
- `0` correções planejadas remanescentes
- `0` contratos ainda marcados para rebuild
- `74` linhas seguem sem match único
- `824` exceções seguem abertas

Detalhe do residual:
- `822` exceções `parcela_not_found`
- `2` exceções `parcela_conflict`
- `70` linhas `no_match`
- `4` linhas `ambiguous_matricula`

## Associados fora da planilha

Listas para tratamento manual:
- [sistema_fora_da_planilha.csv](/mnt/d/apps/abasev2/abasev2/backups/maristela_sheet_20260401T152454_verify3/sistema_fora_da_planilha.csv)
- [sistema_fora_da_planilha_priorizados.csv](/mnt/d/apps/abasev2/abasev2/backups/maristela_sheet_20260401T152454_verify3/sistema_fora_da_planilha_priorizados.csv)

Totais:
- `110` associados do sistema não aparecem na planilha
- `54` desses possuem contrato/parcela tocando o período conciliado e devem ser priorizados
