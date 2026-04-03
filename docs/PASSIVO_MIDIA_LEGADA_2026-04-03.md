# Passivo de Mídia Legada em 03/04/2026

## Resumo executivo

- universo consolidado analisado por arquivo: `2031` referências
- restauradas na primeira varredura recursiva de `anexos_legado/public` e `anexos_legado/storage`: `858`
- restauradas na segunda passada guiada pelo dump legado: `1124`
- total restaurado no lote: `1982`
- saldo real sem arquivo físico após todas as passadas: `49`

## Fontes usadas

- acervo legado em `anexos_legado/public`
- acervo legado em `anexos_legado/storage`
- dump legado carregado temporariamente para inspeção operacional
- relatórios locais de auditoria em `media/relatorios/legacy_import/`

## Tabelas e colunas do dump que ajudaram na reconciliação

- `tesouraria_pagamentos.comprovante_path`
- `tesouraria_pagamentos.comprovante_associado_path`
- `tesouraria_pagamentos.comprovante_agente_path`
- `refinanciamento_comprovantes.path`
- `refinanciamento_solicitacoes.termo_antecipacao_path`
- `pagamentos_mensalidades.manual_comprovante_path`
- `pagamentos_mensalidades.source_file_path`
- `agente_cadastros.documents_json`
- `agente_doc_reuploads.file_relative_path`

## O que fechou

- `tesouraria`: `1264` referências resolvidas no total
- `renovacao`: `680` referências resolvidas no total
- `manual`: `38` referências resolvidas no total
- `cadastro`: `0` resolvidas nesta etapa final
- `esteira`: `0` resolvidas nesta etapa final

Leitura prática:

- `renovacao` e `manual` ficaram zerados no saldo remanescente
- `tesouraria` caiu para apenas `2` comprovantes sem match seguro
- o passivo restante concentrou-se em `cadastro` e `esteira`

## Saldo final remanescente

- `cadastro`: `42`
- `esteira`: `5`
- `tesouraria`: `2`

Total: `49`

## Observações operacionais

- os `42` de cadastro pertencem a `6` associados e todos continuam presentes na planilha da Maristela
- os `5` de esteira não têm `legacy_path` utilizável; são referências internas em `DocIssue.agent_uploads_json`
- os `2` de tesouraria restantes pertencem ao associado `ANTONIO DANILO DE PINHO TEIXEIRA`, contrato `CTR-20250902152309-UEGQC`
- a promoção de mídia restaurada ficou fora do Git; os artefatos operacionais continuam só no filesystem local

## Documentos correlatos

- `docs/ANEXOS_LEGADOS_FALTANTES_2026-04-02.md`
- `docs/ASSOCIADOS_REMANESCENTES_SEM_ARQUIVOS_2026-04-03.md`
- `docs/passivo_midia_legada_2026-04-02.md`
