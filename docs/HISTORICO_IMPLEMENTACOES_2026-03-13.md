# Historico de Implementacoes Ate 13 de Marco de 2026

## Objetivo

Este documento consolida o que foi implementado no projeto ate agora para:

- migracao do legado para o modelo atual
- centralizacao de cadastro do associado
- importacao de arquivo retorno
- reconciliacao financeira e operacional
- refinanciamento
- saneamento de ciclos duplicados
- ajustes de frontend ligados a renovacao de ciclos

O foco aqui e registrar o que foi feito, por que foi feito e qual ficou sendo a regra valida na aplicacao.

## 1. Mapeamento legado x atual

Foi feito o mapeamento entre as tabelas legadas e as tabelas atuais da aplicacao.

Equivalencias principais:

- `agente_cadastros` -> `associados_associado`
- `tesouraria_pagamentos` -> `tesouraria_pagamento`
- `pagamentos_mensalidades` -> `importacao_pagamentomensalidade`
- `refinanciamentos` -> `refinanciamento_refinanciamento`
- `refinanciamento_itens` -> `refinanciamento_item`

Tambem foi validado que:

- `associados_associado` nao era identica ao legado em quantidade nem em colunas
- o modelo atual estava normalizado em varias tabelas auxiliares
- o fluxo atual do sistema gravava o cadastro novo em varias tabelas, nao em uma tabela unica

## 2. Centralizacao do cadastro do associado

O backend e o banco foram ajustados para que o cadastro novo do associado, feito pelo agente, ficasse centralizado em `associados_associado`.

Foi feito:

- inclusao de campos snapshot inspirados em `agente_cadastros`
- persistencia direta dos dados principais do cadastro em `associados_associado`
- serializers de leitura com fallback para dados antigos
- sincronizacao de compatibilidade para endereco, banco, contato e documentos
- migration aplicada no MySQL para suportar o novo formato

Resultado pratico:

- novos cadastros deixam de depender de `associados_endereco`, `associados_dadosbancarios` e `associados_contatohistorico` como origem principal
- o fluxo operacional continua criando contrato, ciclo, parcelas, esteira e documentos quando necessario

## 3. Importacao dos associados legados para o fluxo atual

Foi criada uma carga para trazer os associados do legado para o fluxo atual.

O que foi feito:

- leitura do dump legado
- compatibilizacao de JSON legado escapado
- criacao de associados, contratos, ciclos, parcelas, esteira e documentos no modelo atual
- validacao de idempotencia para nao duplicar em reexecucoes

Resultado validado na epoca da carga:

- todos os CPFs legados passaram a existir em `associados_associado`
- contratos, ciclos e parcelas legados ficaram materializados no fluxo atual
- o importador conseguiu reexecutar em modo de conferencia sem gerar duplicacoes

## 4. Limpeza seletiva de importacao e refinanciamento

Foi criado um management command dedicado para limpeza segura dos dados de importacao e refinanciamento.

Escopo implementado:

- `importacao_pagamentomensalidade`
- `importacao_arquivoretorno`
- `importacao_arquivoretornoitem`
- `importacao_importacaolog`
- `refinanciamento_refinanciamento`
- `refinanciamento_item`

O comando:

- suporta `--dry-run`
- suporta `--execute`
- remove os arquivos fisicos apontados por `arquivo_url`
- usa `TRUNCATE`
- reseta `AUTO_INCREMENT`
- valida dependencias antes de apagar

Depois disso, a limpeza real foi executada no banco atual.

## 5. Correcao da importacao do arquivo retorno

Houve divergencia entre o valor importado no sistema novo e o valor do sistema antigo.

As correcoes aplicadas foram:

- ajuste do parser do arquivo retorno para seguir o padrao do legado
- consolidacao de CPFs duplicados dentro do mesmo arquivo pela primeira ocorrencia valida
- reprocessamento das competencias afetadas no banco real

Base de verdade financeira adotada:

- `importacao_pagamentomensalidade`

Diferenca importante consolidada no sistema:

- `ArquivoRetornoItem` e `resultado_resumo` representam a conciliacao operacional
- `importacao_pagamentomensalidade` representa a leitura financeira consolidada

Isso passou a valer tanto para os endpoints quanto para a UI.

## 6. Alinhamento da UI de importacao e renovacao com o financeiro

Foi corrigido o frontend para usar o resumo financeiro correto quando existir arquivo retorno.

O que mudou:

- cards e detalhamentos passaram a usar o payload financeiro do backend
- exportacoes passaram a seguir o dataset financeiro correto quando aplicavel
- a tela deixou de depender so do resumo operacional salvo no arquivo retorno

Conceito consolidado:

- valores monetarios devem seguir o endpoint financeiro
- indicadores operacionais de ciclo continuam vindo de contrato, ciclo e parcela

## 7. Refinanciamento no padrao legado

Foi reimplementada a regra de refinanciamento com base no comportamento legado.

Regra aplicada:

- o associado fica apto quando possui 3 pagamentos pagos em `importacao_pagamentomensalidade`
- os meses nao precisam ser sequenciais
- o que vale e o `3/3`, nao a sequencia cronologica sem falhas
- os pagamentos usados ficam presos ao refinanciamento por `refinanciamento_item`
- esses pagamentos nao podem ser reutilizados em novo refinanciamento
- a solicitacao cria:
  - 1 registro em `refinanciamento_refinanciamento`
  - 3 registros em `refinanciamento_item`

Tambem foi ajustado:

- o resumo `1/3`, `2/3`, `3/3` na listagem de contratos
- o botao de solicitar refinanciamento no frontend

## 8. Documentacao funcional criada

Foi criado o documento:

- `docs/LOGICA_ARQUIVO_RETORNO_E_RENOVACAO.md`

Esse documento registra:

- importacao do arquivo retorno
- resumo financeiro
- renovacao de ciclo
- refinanciamento no padrao legado

## 9. Normalizacao de ciclos duplicados

Foi identificado um problema estrutural no banco:

- alguns associados possuíam contratos paralelos gerando o mesmo ciclo logico
- na UI isso aparecia como duplicidade, por exemplo dois "Ciclo 1" com o mesmo periodo e status diferentes

O caso usado como referencia foi:

- associado `ACACIO LUSTOSA DANTAS`
- CPF `77852621368`

Foi criado o modulo:

- `backend/apps/contratos/cycle_normalization.py`

E o comando:

- `python manage.py normalize_duplicate_cycles`

Regra da normalizacao:

- agrupar por associado + numero do ciclo + data_inicio + data_fim
- escolher o ciclo canonico pelo melhor contrato e maior progresso
- reatribuir itens de retorno quando necessario
- fechar o ciclo duplicado
- cancelar o contrato duplicado
- ignorar contratos ja cancelados na visualizacao

Execucao realizada no banco real:

- `156` grupos duplicados tratados
- `156` ciclos duplicados consolidados
- `0` grupos duplicados restantes

No caso do Acacio:

- contrato `2305` foi cancelado
- ciclo `2305` foi fechado
- permaneceu um unico ciclo valido no contrato `438`

## 10. Contagem logica de ciclos e ajustes de API

Depois da normalizacao, tambem foram ajustadas as APIs para nao voltar a mostrar duplicidade logica.

Foi feito:

- deduplicacao na action `associados/{id}/ciclos`
- inclusao de `contrato_id`, `contrato_codigo` e `contrato_status` no serializer do ciclo
- contagem logica de ciclos abertos e fechados na listagem de associados

Impacto:

- a listagem de associados deixa de contar contratos cancelados como ciclos validos
- a aba de ciclos no frontend passa a exibir o ciclo real e o contrato associado

## 11. Correcao do resumo mensal de renovacao

Foi identificado que os cards da rota `renovacao-ciclos` estavam com `Renovados` e `Aptos a renovar` zerados.

Motivo:

- a regra de status visual priorizava `ciclo_iniciado`
- `ciclo_renovado` e `apto_a_renovar` ficavam escondidos pelo calculo anterior

Correcao aplicada:

- `ciclo.status == ciclo_renovado` agora conta como `ciclo_renovado`
- `ciclo.status == apto_a_renovar` agora conta como `apto_a_renovar`
- o resumo mensal passou a contar cada status explicitamente

Validacao no backend apos a correcao:

- `12/2025`: `81` renovados, `147` aptos, `4` inadimplentes
- `01/2026`: `81` renovados, `82` aptos, `137` inadimplentes
- `02/2026`: `81` renovados, `19` em aberto, `81` ciclos iniciados, `71` inadimplentes

## 12. Estado funcional consolidado antes do novo ajuste de UI

Ao final das correcoes acima, o sistema ficou assim:

- cadastro novo centralizado em `associados_associado`
- legado importado para o fluxo atual
- limpeza de importacao/refinanciamento disponivel por comando
- parser financeiro alinhado ao legado
- frontend financeiro alinhado ao backend
- refinanciamento por 3 pagamentos livres implementado
- ciclos duplicados saneados no banco real
- contagem de ciclos consolidada na API
- renovacao mensal deixando de zerar `renovados` e `aptos`

## 13. Arquivos principais tocados ate aqui

Backend:

- `backend/apps/associados/models.py`
- `backend/apps/associados/services.py`
- `backend/apps/associados/serializers.py`
- `backend/apps/associados/views.py`
- `backend/apps/accounts/management/commands/import_legacy_associados_current_flow.py`
- `backend/apps/accounts/management/commands/cleanup_finance_domain_data.py`
- `backend/apps/accounts/management/commands/import_legacy_data.py`
- `backend/apps/importacao/parsers.py`
- `backend/apps/importacao/services.py`
- `backend/apps/importacao/financeiro.py`
- `backend/apps/importacao/views.py`
- `backend/apps/contratos/renovacao.py`
- `backend/apps/contratos/serializers.py`
- `backend/apps/contratos/views.py`
- `backend/apps/contratos/cycle_normalization.py`
- `backend/apps/contratos/management/commands/normalize_duplicate_cycles.py`
- `backend/apps/refinanciamento/payment_rules.py`
- `backend/apps/refinanciamento/services.py`
- `backend/apps/refinanciamento/serializers.py`

Frontend:

- `apps/web/src/app/(dashboard)/importacao/page.tsx`
- `apps/web/src/app/(dashboard)/renovacao-ciclos/page.tsx`
- `apps/web/src/app/(dashboard)/associados/page.tsx`
- `apps/web/src/app/(dashboard)/agentes/meus-contratos/page.tsx`
- `apps/web/src/lib/importacao-financeiro.ts`
- `apps/web/src/lib/api/types.ts`

Testes:

- `backend/apps/accounts/tests/test_cleanup_finance_domain_data.py`
- `backend/apps/accounts/tests/test_import_legacy_associados_current_flow.py`
- `backend/apps/accounts/tests/test_import_legacy_data.py`
- `backend/apps/contratos/tests/test_cycle_normalization.py`
- `backend/apps/contratos/tests/test_renovacao.py`
- `backend/apps/refinanciamento/tests/test_refinanciamento_pagamentos.py`
- `apps/web/src/app/(dashboard)/importacao/page.test.tsx`
- `apps/web/src/app/(dashboard)/renovacao-ciclos/page.test.tsx`

## 14. Proximo bloco de trabalho

O proximo ajuste solicitado apos este historico e focado em frontend:

- refino visual e de tipografia na rota `renovacao-ciclos`
- cards KPI clicaveis com modal por status
- listagem completa dos arquivos retorno em cards
- reorganizacao dos filtros dessa rota
- simplificacao global do header com busca maior e autocomplete
