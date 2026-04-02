# Passivo de Mídia Legada em 02/04/2026

## Resolvido neste lote

- 4 comprovantes de renovação foram encontrados em `anexos_legado/CONCILIACAO_ANEXOS_FINAIS_2026-04-02` e copiados para o diretório canônico de mídia.
- Auditoria consolidada gerada em `media/relatorios/legacy_import/audit_after_manual_copy.json`.
- Auditoria completa gerada em `media/relatorios/legacy_import/audit_full_after_manual_copy.json`.

Arquivos restaurados:

- `refinanciamentos/renovacoes/CTR-20250912162307-TLGCV/associado/256b417c8b_-ac74-41870c647ce2.jpeg`
- `refinanciamentos/renovacoes/CTR-20250912162307-TLGCV/agente/39195332b2_-9c01-99064088bcef.jpeg`
- `refinanciamentos/renovacoes/CTR-20250912163147-X9CFZ/associado/681348067d_-87fa-7259ba785086.jpeg`
- `refinanciamentos/renovacoes/CTR-20250912163147-X9CFZ/agente/fbc79013eb_-a72b-c309fddcb7bd.jpeg`

## Estado oficial após a auditoria final

- `cadastro`: 42 registros `reference_only`
- `renovacao`: 680 registros `reference_only`
- `manual`: 38 registros `reference_only`
- `esteira`: 5 registros `reference_only`
- `tesouraria`: 0 registros `reference_only`
- `no_path`: 94 registros sem caminho legado utilizável

Total consolidado:

- `records`: 6316
- `already_canonical`: 4894
- `reference_only`: 765
- `no_path`: 94

## Pendente

- Os 42 documentos de cadastro listados em `docs/ANEXOS_LEGADOS_FALTANTES_2026-04-02.md` continuam sem arquivo físico localizável.
- A busca foi feita de forma recursiva no workspace disponível, incluindo subpastas de `anexos_legado`, nomes exatos e prefixos de timestamp.
- Até este ponto, esses 42 documentos não foram encontrados fisicamente no acervo acessível.

## Próximo passo operacional

- Resolver o passivo restante por família usando o relatório `audit_full_after_manual_copy.json` como fonte de verdade.
- Quando novos arquivos surgirem no legado, copiar primeiro para o diretório canônico e só depois reexecutar a auditoria final.
