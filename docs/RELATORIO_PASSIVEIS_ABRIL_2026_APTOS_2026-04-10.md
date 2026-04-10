# Conferência de Passíveis de Renovação de Abril de 2026

- Fonte: `Controle e Conciliação de Mensalidades_ABASE - RENOVAÇÃO PARCIAL ABRIL.csv`
- Total marcados como `PASSIVEL DE RENOVAÇÃO`: `97`
- Presentes na rota `Aptos a renovar`: `17`
- Fora da rota `Aptos a renovar`: `80`

## Quebra dos fora da rota por motivo
- `status_renovacao_apto_mas_nao_listado`: `45`
- `sem_contrato_operacional`: `18`
- `status_visual=ciclo_aberto`: `10`
- `status_visual=ciclo_com_pendencia`: `4`
- `status_visual=aprovado_para_renovacao`: `2`
- `associado_ausente`: `1`

## Quebra por status visual atual
- `apto_a_renovar`: `45`
- `vazio`: `19`
- `ciclo_aberto`: `10`
- `ciclo_com_pendencia`: `4`
- `aprovado_para_renovacao`: `2`

## Quebra por status de renovação atual
- `apto_a_renovar`: `45`
- `vazio`: `33`
- `aprovado_para_renovacao`: `2`

## Leitura objetiva
- O maior grupo fora da rota é de contratos que já estão com `status_renovacao = apto_a_renovar`, mas não entram na tela de abril.
- Dentro desse grupo, o principal indício é divergência da própria listagem de renovação: muitos não geram linha de abril na consulta da rota.
- O segundo grupo relevante é o universo de 30/50 sem contrato operacional, alinhado com a regra recente de não levar esse perfil para aptos.
- Há um grupo menor que hoje está fora por `ciclo_aberto`, `ciclo_com_pendencia` ou já em `aprovado_para_renovacao`.

A lista nominal completa dos `80` fora da rota está na CSV ao lado.

