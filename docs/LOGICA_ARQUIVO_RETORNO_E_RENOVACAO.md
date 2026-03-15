# Logica Atual de Arquivo Retorno, Renovacao de Ciclo e Refinanciamento

## Objetivo

Este documento descreve a regra atual da aplicacao para:

- importacao de arquivo retorno
- reconciliacao operacional das parcelas e ciclos
- resumo financeiro mensal mostrado na UI
- renovacao de ciclo
- refinanciamento no padrao legado

O objetivo e registrar a regra que esta hoje no codigo, usando os nomes legado e atual, para evitar regressao futura.

## Mapa de nomes: legado x atual

| Conceito legado | Tabela legado | Tabela atual |
| --- | --- | --- |
| Pagamentos importados do retorno | `pagamentos_mensalidades` | `importacao_pagamentomensalidade` |
| Arquivo retorno | nao havia essa separacao formal | `importacao_arquivoretorno` |
| Linhas do arquivo retorno | nao havia essa separacao formal | `importacao_arquivoretornoitem` |
| Log de importacao | nao havia essa separacao formal | `importacao_importacaolog` |
| Refinanciamentos | `refinanciamentos` | `refinanciamento_refinanciamento` |
| Itens do refinanciamento | `refinanciamento_itens` | `refinanciamento_item` |

## Visao geral do fluxo

Hoje existem duas camadas diferentes a partir do arquivo retorno:

1. Camada operacional
Grava o arquivo, cria `ArquivoRetornoItem`, tenta localizar associado/parcela, baixa parcela, marca inadimplencia, encerra ciclo e abre novo ciclo quando necessario.

2. Camada financeira
Faz upsert em `importacao_pagamentomensalidade`, que e a base de pagamentos consolidados por `cpf_cnpj + competencia`.
Essa camada e a referencia para os valores financeiros mostrados no sistema e para a regra de refinanciamento.

Essas duas camadas convivem. Elas nao sao a mesma coisa.

## 1. Importacao do arquivo retorno

Implementacao principal:

- [services.py](/mnt/d/apps/abasev2/abasev2/backend/apps/importacao/services.py)
- [parsers.py](/mnt/d/apps/abasev2/abasev2/backend/apps/importacao/parsers.py)
- [validators.py](/mnt/d/apps/abasev2/abasev2/backend/apps/importacao/validators.py)

### Passo a passo

1. O upload recebe o arquivo em `/api/v1/importacao/arquivo-retorno/upload/`.
2. O arquivo e validado:
   - tamanho
   - formato
   - cabecalho
3. O arquivo e salvo no storage e cria um registro em `importacao_arquivoretorno`.
4. O parser le o arquivo e extrai:
   - metadados do cabecalho
   - linhas de detalhe
   - warnings de parse
5. Antes de persistir as linhas, CPFs duplicados no mesmo arquivo sao consolidados no padrao legado:
   - a primeira ocorrencia do CPF e mantida
   - as demais sao ignoradas
   - isso fica registrado em `importacao_importacaolog`
6. As linhas validas sao gravadas em `importacao_arquivoretornoitem`.
7. A reconciliacao operacional e executada sobre os itens.
8. Em paralelo, os pagamentos consolidados sao criados ou atualizados em `importacao_pagamentomensalidade`.
9. O arquivo e finalizado com `status=concluido` e `resultado_resumo`.

## 2. Reconciliacao operacional do retorno

Implementacao principal:

- [reconciliacao.py](/mnt/d/apps/abasev2/abasev2/backend/apps/importacao/reconciliacao.py)

### O que a reconciliacao faz

Cada `ArquivoRetornoItem` tenta:

1. localizar o associado por CPF, matricula, nome e orgao
2. localizar a parcela da competencia
3. decidir o resultado operacional da linha

### Resultados possiveis da linha

- `baixa_efetuada`
- `nao_descontado`
- `pendencia_manual`
- `nao_encontrado`
- `erro`
- `ciclo_aberto`

### Regras por codigo de status do retorno

- `1`: efetivado
- `4`: efetivado com diferenca
- `2`, `3`, `S`: nao descontado
- `5`, `6`: pendencia manual

### Efeitos operacionais

#### Quando a linha e efetivada

- a parcela vai para `descontado`
- `data_pagamento` e preenchida se necessario
- a observacao da parcela recebe nota de baixa automatica
- se todas as parcelas do ciclo ficarem `descontado`:
  - o ciclo atual vai para `ciclo_renovado`
  - o proximo ciclo e aberto, se ja existir e estiver apto
  - ou um novo ciclo e criado automaticamente com 3 parcelas

#### Quando a linha e nao descontada

- a parcela vai para `nao_descontado`
- o associado vai para `inadimplente`
- o motivo fica registrado

#### Quando a linha vira pendencia manual

- a parcela futura pode ser movida para `em_aberto`
- o item fica pendente para conferencia manual

### Importante

O `resultado_resumo` salvo em `importacao_arquivoretorno` e um resumo operacional de reconciliacao.
Ele nao e o resumo financeiro final mostrado nos cards principais.

## 3. Upsert de pagamentos consolidados

Implementacao principal:

- [services.py](/mnt/d/apps/abasev2/abasev2/backend/apps/importacao/services.py)

### Base de verdade financeira

A tabela que consolida os pagamentos do retorno e:

- `importacao_pagamentomensalidade`

Ela representa a versao atual da tabela legado `pagamentos_mensalidades`.

### Regra de upsert

O upsert e feito por:

- `cpf_cnpj`
- `referencia_month`

Ou seja, o sistema entende que existe no maximo um pagamento consolidado por CPF e competencia.

### Regras aplicadas

- se ja existir `cpf + competencia`, nao duplica:
  - mantem o registro existente
  - faz backfill de `associado` se ainda estiver vazio
  - aplica snapshot manual legado se existir
- se nao existir, cria novo registro
- o campo `source_file_path` guarda o arquivo de origem
- o campo `import_uuid` identifica a rodada de importacao

### Snapshot legado manual

Ao importar, o sistema tenta reaplicar informacoes manuais legadas quando existirem:

- `manual_status`
- `esperado_manual`
- `recebido_manual`
- `manual_paid_at`
- `manual_forma_pagamento`
- `manual_comprovante_path`
- `agente_refi_solicitado`

Isso preserva o comportamento do sistema antigo quando havia baixa manual ou comprovacao manual fora do retorno.

## 4. Resumo financeiro mensal

Implementacao principal:

- [financeiro.py](/mnt/d/apps/abasev2/abasev2/backend/apps/importacao/financeiro.py)
- endpoint `/api/v1/importacao/arquivo-retorno/{id}/financeiro/`

### Regra

O resumo financeiro nao sai de `ArquivoRetornoItem`.
Ele sai de `importacao_pagamentomensalidade` filtrando pela competencia.

### O que conta como pagamento valido

Um pagamento e considerado concluido se:

- `status_code` estiver em `1` ou `4`
- ou `manual_status` estiver como pago

### Como o valor recebido e calculado

- se foi pago manualmente, usa `recebido_manual`, com fallback para o valor esperado
- se foi pago pelo arquivo, usa o valor do proprio registro
- se nao foi pago, o recebido e `0`

### Categorias usadas no resumo

- `mensalidades`: valores >= `100.00`
- `valores_30_50`: valores `30.00` ou `50.00`
- `outros`: resto

### Distincao importante

Hoje a UI trabalha com dois tipos de resumo:

1. Resumo operacional
Vem de `ArquivoRetorno.resultado_resumo`.

2. Resumo financeiro
Vem do endpoint `/financeiro/`, calculado em cima de `importacao_pagamentomensalidade`.

Quando houver divergencia entre operacional e financeiro, o card financeiro deve seguir `PagamentoMensalidade`, nao `ArquivoRetornoItem`.

## 5. Renovacao de ciclo

Implementacao principal:

- [renovacao.py](/mnt/d/apps/abasev2/abasev2/backend/apps/contratos/renovacao.py)

### O que e renovacao de ciclo na aplicacao

Renovacao de ciclo e a evolucao operacional do contrato quando um ciclo fecha `3/3`.

Na pratica:

- o ciclo atual pode virar `ciclo_renovado`
- o proximo ciclo pode ser criado ou aberto
- as parcelas do novo ciclo passam a existir e podem ir para `em_aberto`

### Fonte dos dados da tela Renovacao de Ciclos

A tela mistura duas visoes:

1. Detalhamento operacional por parcela/ciclo
Sai de `contratos`, `ciclos`, `parcelas` e do ultimo `ArquivoRetornoItem` da competencia.

2. Resumo financeiro mensal
Quando existe arquivo retorno para a competencia, os valores financeiros devem seguir o payload `/financeiro/`.

### Status visuais usados na renovacao

- `ciclo_renovado`
- `apto_a_renovar`
- `em_aberto`
- `ciclo_iniciado`
- `inadimplente`

Importante: essa area e operacional. Ela nao substitui o fluxo explicito de refinanciamento.

## 6. Refinanciamento no padrao legado

Implementacao principal:

- [payment_rules.py](/mnt/d/apps/abasev2/abasev2/backend/apps/refinanciamento/payment_rules.py)
- [strategies.py](/mnt/d/apps/abasev2/abasev2/backend/apps/refinanciamento/strategies.py)
- [services.py](/mnt/d/apps/abasev2/abasev2/backend/apps/refinanciamento/services.py)

### Conceito

No negocio, refinanciamento e a renovacao controlada por regra de pagamento.
Na implementacao atual, ele usa os pagamentos consolidados do retorno, no mesmo conceito do legado:

- 3 pagamentos validos habilitam o refinanciamento
- os meses nao precisam ser sequenciais
- os 3 pagamentos usados ficam travados naquele refinanciamento

Exemplo valido:

- janeiro
- fevereiro
- abril

Isso ja forma `3/3`.

### Fonte de elegibilidade

A elegibilidade nao sai mais das parcelas do ciclo.
Ela sai de `importacao_pagamentomensalidade`.

Um pagamento entra na conta se:

- `status_code` estiver em `1` ou `4`
- ou `manual_status` estiver `pago`

### O que significa pagamento livre

Pagamento livre e um `PagamentoMensalidade` que:

- pertence ao associado ou ao CPF dele
- esta pago
- ainda nao foi consumido por `refinanciamento_item`

### Regra de bloqueio

Se ja existir refinanciamento ativo para o CPF, um novo nao pode ser solicitado.

Status considerados ativos:

- `pendente_apto`
- `concluido`
- `efetivado`
- `solicitado`
- `em_analise`
- `aprovado`

### O que acontece ao solicitar refinanciamento

Quando o admin ou agente aciona a solicitacao:

1. o sistema busca os 3 primeiros pagamentos livres, ordenados por `referencia_month`
2. monta o `cycle_key` no formato legado `YYYY-MM|YYYY-MM|YYYY-MM`
3. grava um registro em `refinanciamento_refinanciamento`
4. grava 3 registros em `refinanciamento_item`
5. marca esses pagamentos com `agente_refi_solicitado=True`
6. cria um `ciclo_destino` com 3 novas parcelas
7. define a proxima competencia como o mes seguinte ao pagamento mais recente usado

### Campos legados preservados no refinanciamento

O registro principal recebe:

- `mode`
- `cycle_key`
- `ref1`
- `ref2`
- `ref3`
- `cpf_cnpj_snapshot`
- `nome_snapshot`
- `agente_snapshot`
- `contrato_codigo_origem`
- `contrato_codigo_novo`
- `parcelas_ok`
- `parcelas_json`

### Por que existe `refinanciamento_item`

`refinanciamento_item` e obrigatorio para garantir duas coisas:

1. saber exatamente quais 3 pagamentos formaram aquele refinanciamento
2. impedir reutilizacao desses mesmos pagamentos em outro refinanciamento futuro

Sem essa linkagem, o sistema poderia reutilizar meses antigos e criar refinanciamentos incorretos.

## 7. Relacao entre renovacao de ciclo e refinanciamento

Os dois conceitos se cruzam, mas nao sao identicos no codigo.

### Renovacao de ciclo

- e uma consequencia operacional do fechamento de um ciclo
- trabalha com `Contrato`, `Ciclo`, `Parcela` e `ArquivoRetornoItem`
- pode abrir ou criar o proximo ciclo automaticamente

### Refinanciamento

- e um fluxo explicito e auditavel
- trabalha com `PagamentoMensalidade`, `Refinanciamento` e `Item`
- exige 3 pagamentos livres
- impede reutilizacao de pagamentos ja consumidos
- gera aprovacao, bloqueio e efetivacao

### Leitura recomendada

No negocio, pode-se dizer que refinanciamento e a renovacao controlada do associado apos `3/3`.
No codigo, porem, a renovacao operacional do ciclo e uma camada, e o refinanciamento auditavel e outra.

## 8. Endpoints mais importantes

### Importacao

- `POST /api/v1/importacao/arquivo-retorno/upload/`
- `POST /api/v1/importacao/arquivo-retorno/{id}/reprocessar/`
- `GET /api/v1/importacao/arquivo-retorno/{id}/financeiro/`
- `GET /api/v1/importacao/arquivo-retorno/{id}/descontados/`
- `GET /api/v1/importacao/arquivo-retorno/{id}/nao-descontados/`
- `GET /api/v1/importacao/arquivo-retorno/{id}/pendencias-manuais/`

### Contratos / elegibilidade

- `GET /api/v1/contratos/`
- `GET /api/v1/contratos/resumo/`

### Refinanciamento

- `GET /api/v1/refinanciamentos/{contrato_id}/elegibilidade/`
- `POST /api/v1/refinanciamentos/{contrato_id}/solicitar/`
- `POST /api/v1/refinanciamentos/{refinanciamento_id}/aprovar/`
- `POST /api/v1/refinanciamentos/{refinanciamento_id}/bloquear/`
- `POST /api/v1/refinanciamentos/{refinanciamento_id}/efetivar/`

## 9. Regras que nao podem ser quebradas

- CPF duplicado no mesmo arquivo retorno deve ser consolidado no padrao legado.
- `importacao_pagamentomensalidade` e a base de verdade do resumo financeiro.
- `ArquivoRetorno.resultado_resumo` e operacional, nao financeiro.
- Refinanciamento deve ser baseado em 3 pagamentos livres, nao em 3 parcelas descontadas do ciclo.
- Os 3 pagamentos do refinanciamento nao precisam ser sequenciais.
- Um pagamento ja vinculado em `refinanciamento_item` nao pode ser reutilizado.
- O `cycle_key` do refinanciamento deve refletir exatamente os meses consumidos.
- A proxima competencia do refinanciamento deve ser o mes seguinte ao pagamento mais recente usado.

## 10. Arquivos principais para manutencao futura

- [backend/apps/importacao/services.py](/mnt/d/apps/abasev2/abasev2/backend/apps/importacao/services.py)
- [backend/apps/importacao/reconciliacao.py](/mnt/d/apps/abasev2/abasev2/backend/apps/importacao/reconciliacao.py)
- [backend/apps/importacao/financeiro.py](/mnt/d/apps/abasev2/abasev2/backend/apps/importacao/financeiro.py)
- [backend/apps/contratos/renovacao.py](/mnt/d/apps/abasev2/abasev2/backend/apps/contratos/renovacao.py)
- [backend/apps/refinanciamento/payment_rules.py](/mnt/d/apps/abasev2/abasev2/backend/apps/refinanciamento/payment_rules.py)
- [backend/apps/refinanciamento/strategies.py](/mnt/d/apps/abasev2/abasev2/backend/apps/refinanciamento/strategies.py)
- [backend/apps/refinanciamento/services.py](/mnt/d/apps/abasev2/abasev2/backend/apps/refinanciamento/services.py)

