# Auditoria de Rebuild de Ciclos

Data da conferência: `2026-04-09`  
Base analisada: banco atual no container `abase-v2-backend-1`

## Resultado
- Total de contratos operacionais auditados: `777`
- Contratos que realmente precisam de rebuild: `139`
- Contratos que não precisam de rebuild: `638`
- Contratos manuais na fila de rebuild: `0`
- Caso `Justino` na fila de rebuild: `não`

## Critérios usados
- `ciclo_antigo_com_status_invalido_no_bucket_cycle`
  - contrato com mais de um ciclo
  - parcela de ciclo antigo ainda persistida no bucket `cycle`
  - status inválido para permanecer dentro do ciclo: `nao_descontado`, `em_previsao` ou `quitada`
- `competencia_duplicada_ativa`
  - mesma competência ativa em mais de uma parcela do mesmo contrato
- Também conferido e sem pendência no recorte atual:
  - competências antes de `10/2025`
  - previsões vencidas persistidas
  - documentos existentes no banco e ausentes na projeção

## Resumo das inconsistências
- `139` contratos com `ciclo_antigo_com_status_invalido_no_bucket_cycle`
- `1` contrato com `competencia_duplicada_ativa`
- `0` contratos com competência antes de outubro
- `0` contratos com previsão vencida persistida
- `0` contratos com documentos do ciclo sumindo na projeção

## Leitura operacional
- A fila de rebuild não é geral. Ela ficou concentrada em contratos `não manuais`.
- O problema predominante é estrutural no dado persistido: parcelas de ciclos antigos ainda ficaram no bucket `cycle`.
- Isso indica rebuild seletivo dos `139` contratos do CSV, não rebuild em massa da base inteira.

## Casos mais pesados
- `JOSE LOUREDAN PINHEIRO GOMES` `[CTR-20250902114310-ZWQYM]` com `4` linhas inválidas em ciclo antigo
- `ANTONIO DANILO DE PINHO TEIXEIRA` `[CTR-20250902152309-UEGQC]` com `3` linhas inválidas
- `AUREA CRISTINA SOUSA RODRIGUES` `[CTR-20250902124951-1XLK0]` com `3` linhas inválidas
- `UBIRAJARA DE SOUSA ROCHA` `[CTR-20251009134547-V65BR]` com linha inválida e duplicidade ativa de competência

## Arquivo completo
- Lista completa dos candidatos a rebuild: [REBUILD_CICLOS_CANDIDATOS_2026-04-09.csv](/mnt/d/apps/abasev2/abasev2/docs/REBUILD_CICLOS_CANDIDATOS_2026-04-09.csv)

## Colunas do CSV
- `contrato_id`
- `contrato_codigo`
- `associado_nome`
- `cpf`
- `manual_layout`
- `issues`
- `cycle_rows_to_fix`
- `duplicate_refs`
- `missing_docs`
