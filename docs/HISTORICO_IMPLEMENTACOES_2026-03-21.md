# Historico de Implementacoes de 21 de Marco de 2026

## Objetivo

Este documento consolida o que foi implementado no web novo em 21 de marco de 2026.

O foco deste pacote foi:

- ajustes de perfil e permissao para agente
- reorganizacao de rotas e navegacao
- novos KPIs e filtros avancados
- ajustes do modulo de analise
- correcao de timezone e typecheck
- importacao legada, enriquecimento pos-importacao e regra de ciclos
- auditoria e correcao de conflito entre baixa manual e arquivo retorno em fevereiro de 2026

## 1. Agente, cadastro e detalhes do associado

Foi restringida a visao do perfil `AGENTE` no detalhe do associado e no detalhe de parcela/ciclo.

Regras aplicadas:

- no detalhe do associado, agente ve apenas cabecalho basico, contato e contratos/ciclos
- dados pessoais completos, endereco, dados bancarios, documentos gerais e historico de esteira deixam de ser expostos para agente
- no clique do mes/ciclo, agente ve apenas comprovantes dele mesmo
- comprovantes do associado e anexos administrativos deixam de ser enviados no payload para agente

Tambem foram implementados:

- filtro de agentes ativos por dropdown no cadastro e nos filtros avancados
- etapa 5 do cadastro com selecao de agente e percentual de repasse para perfis acima de agente
- recalculo de comissao do agente a partir do percentual informado

## 2. Navegacao, nomes de rotas e KPIs operacionais

Foi reorganizada a navegacao do modulo de cadastro e das rotas operacionais.

Mudancas principais:

- `Esteira` passou a ser exibida como `Esteira de pendencias`
- `Refinanciados` foi movida para o agrupamento de `Cadastros`
- `Meus Pagamentos` passou a ficar em `Cadastros` para o perfil agente e deixou de aparecer em `Financeiro`
- o card de upload `Divulgacao` foi removido do cadastro de associado

KPIs adicionados ou ajustados:

- `Meus Contratos` com cards clicaveis e card de `Liquidados`
- `Associados` com cards clicaveis e card de `Liquidados`
- `Meus Pagamentos` com cards KPI
- `Esteira de pendencias` com cards KPI
- `Refinanciados` com cards KPI
- `Contratos para Renovacao` com cards KPI

Modais e detalhamento:

- os cards KPI de contratos e associados passaram a abrir modal com tabela operacional
- `Meus Pagamentos` passou a exibir badge de notificacao quando a tesouraria realiza pagamento para o agente

## 3. Refinanciamento e rota do agente

Foi corrigida a rota `Refinanciados` do agente.

O que mudou:

- exibicao de nome, CPF e matricula do associado
- melhoria de colunas de ciclo e referencias
- exibicao apenas do anexo do agente quando aplicavel
- separacao entre contratos refinanciados/efetivados e contratos aptos a renovar
- ajuste do backend para filtrar por status de renovacao e retornar o resumo coerente com a tabela

## 4. Dashboard de analise e fluxo do analista

O modulo de analise foi reorganizado no backend e no frontend.

Mudancas aplicadas:

- nova taxonomia de secoes:
  - ver todos
  - pendencias
  - pendencias corrigidas
  - enviado para tesouraria
  - enviado para coordenacao
  - efetivados
  - cancelados
- os cards KPI passaram a rolar visualmente ate a secao correspondente
- cada linha da fila ganhou botao `Ver detalhes` para abrir o associado completo
- o modal `Ver documentos` passou a mostrar documentos com contexto resumido do cadastro
- as secoes `Ajuste de dados`, `Margem de competencia` e `Ajuste de pagamentos` foram removidas da dashboard
- a rota antes chamada `Aptos` passou a ser exibida como `Contratos para Renovacao`

## 5. Timezone e validacao de frontend

Foi corrigido o timezone do sistema para `America/Fortaleza`.

Itens ajustados:

- `docker-compose.yml`
- `docker/frontend/Dockerfile`
- formatadores de data no frontend
- testes que dependiam do timezone local

Tambem foi corrigida a infraestrutura de typecheck do frontend:

- remocao do `ignoreDeprecations` invalido no `tsconfig`
- criacao de configuracao dedicada para `typecheck`
- ajuste de tipagens que impediam o `tsc --noEmit`
- validacao do `pnpm type-check`

## 6. Importacao legada e enriquecimento pos-importacao

Foi consolidado um fluxo de 2 estagios para dados legados:

- estagio 1: importacao fiel ao dump legado
- estagio 2: enriquecimento canonico do web novo

Acoes realizadas:

- importacao completa da base do dump `abase_dump_legado_21.03.2026.sql`
- verificacao de consistencia da importacao oficial
- sincronizacao de renovações legadas
- sincronizacao de pagamentos iniciais
- sincronizacao de campos manuais de pagamentos mensais
- criacao de um orquestrador de enriquecimento pos-importacao
- documentacao do fluxo em `docs/importacao_legado.md`

## 7. Regra canonica de ciclos

O motor de ciclos foi refeito para seguir a regra operacional definida para o web novo.

Regras consolidadas:

- o tamanho do ciclo respeita o contrato do associado: `3` ou `4`
- dentro do ciclo so podem existir parcelas `descontado` ou `em previsao`
- competencias vencidas e nao descontadas saem do ciclo
- essas competencias passam a aparecer na secao de parcelas nao descontadas
- lacunas sem row explicita no retorno passam a ser inferidas como `implicit_gap`
- ciclo renovado passa a ser exibido como `Concluido`
- ajustes de margem e espacamento dos cards de ciclos foram aplicados na interface

Baixas manuais:

- baixa manual nao recompõe ciclo automaticamente
- ela permanece fora do ciclo ate existir regra explicita de promocao para desconto automatico
- quando a baixa manual representa conflito com retorno automatico efetivado, o retorno passa a ser a verdade

## 8. Auditoria de fevereiro de 2026: baixa manual x retorno

Foi identificada divergencia em `02/2026`:

- diversas parcelas estavam como baixa manual
- parte majoritaria delas ja constava como efetivada no arquivo retorno

Correcao implementada:

- criacao da regra de precedencia do retorno efetivado sobre a baixa manual
- criacao do reparo em lote `repair_manual_return_conflicts`
- reprocessamento dos itens de retorno afetados
- rebuild dos contratos impactados

Resultado executado no banco:

- `108` pagamentos auditados
- `105` convertidos de manual para automatico
- `105` contratos rebuildados
- `105` itens de retorno reprocessados
- `3` casos rejeitados preservados para revisao manual

Caso de referencia:

- o associado `ACACIO LUSTOSA DANTAS`, CPF `77852621368`, passou a ter `fev/2026` incorporado ao `Ciclo 1`
- a competencia deixou de ficar classificada como baixa manual

## 9. Validacoes executadas

Durante o dia foram executadas validacoes de backend e frontend.

Entre elas:

- suites de testes de `associados`, `tesouraria`, `esteira`, `refinanciamento`, `contratos` e `importacao`
- `pnpm --filter @abase/web exec tsc --noEmit`
- `pnpm type-check`
- verificacoes de importacao legada e enriquecimento pos-importacao
- healthcheck da API em `/api/v1/health/`

## 10. Observacoes operacionais

- mobile e legado visual ficaram fora do escopo funcional desta entrega
- a logica nova de importacao legada ficou documentada para futuras reexecucoes
- backend e frontend foram reiniciados ao final das alteracoes relevantes para refletir as mudancas em runtime
