# Anexos Legados por Referência

Alguns anexos exibidos no sistema atual vieram apenas como caminho textual do legado e nao como arquivo fisico importado para o storage atual.

Casos cobertos hoje:
- comprovantes de renovacao legados vindos de `refinanciamento_comprovantes.path`
- termos de antecipacao legados vindos de `refinanciamento_solicitacoes.termo_antecipacao_path`
- comprovantes de baixa manual legados vindos de `pagamentos_mensalidades.manual_comprovante_path`

Comportamento atual:
- quando o arquivo existe no storage atual, o frontend renderiza link clicavel
- quando o arquivo nao existe localmente, o frontend mostra apenas a referencia textual do caminho legado
- o sistema nao deve renderizar link quebrado para esses casos

Março de 2026:
- o PDF `mes_retorno_ref_2026-03.pdf` e tratado como relatorio mensal da competencia
- ele aparece como evidencia de baixa manual da competencia
- ele nao substitui comprovantes individuais inexistentes

Para tornar anexos legados clicaveis no futuro, sera necessario importar o acervo fisico correspondente para o storage configurado em `MEDIA_ROOT`.
