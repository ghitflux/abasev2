# Checklist Manual Web E2E por Fluxo

Atualizado em 2026-03-22.

## Objetivo

Validar manualmente a aplicacao web do inicio ao fim, respeitando a ordem real de operacao por papel:

1. autenticacao e guards
2. agente
3. analista
4. coordenacao
5. tesouraria
6. admin

Este documento nao substitui os checklists historicos. Ele serve como roteiro unico de QA funcional para percorrer as rotas atuais do App Router e confirmar os fluxos principais, permissao por papel, transicao entre etapas e regressao visual/comportamental.

## Referencias

- `docs/CHECKLIST_COMPLETO_ABASE_V2.md`: historico macro de entregas por semana
- `docs/QA_SEMANA_4.md`: checklist manual focado em importacao/arquivo retorno

## Escopo

Este checklist cobre:

- rotas web atuais em `apps/web/src/app`
- fluxos principais por papel
- aliases legados `/pagamentos` e `/renovacoes`
- comportamento esperado de redirecionamento e guardas
- verificacao manual de modulos recentes:
  - dashboard executivo
  - importacao
  - renovacao de ciclo
  - tesouraria
  - baixa manual
  - liquidacoes
  - devolucoes
  - editor admin no detalhe do associado

Este checklist nao cobre:

- testes tecnicos de backend/CLI
- cobertura automatizada
- auditoria de banco por SQL
- testes mobile legado

## Ambiente Minimo

- `docker compose up -d`
- `backend`, `frontend`, `mysql` e `redis` saudaveis
- acesso ao frontend em `http://localhost:3000`
- base com dados de teste minimamente coerentes
- arquivos de apoio disponiveis para upload quando aplicavel:
  - comprovantes PDF/JPG/PNG
  - arquivo retorno `.txt`

## Usuarios de Teste

Separar pelo menos um usuario por papel:

| Papel | Uso principal |
| --- | --- |
| `ADMIN` | validar acesso total, dashboard, relatorios, usuarios, importacao e editor admin |
| `AGENTE` | cadastro novo, esteira, meus contratos, meus pagamentos, refinanciados |
| `ANALISTA` | dashboard de analise e contratos para renovacao |
| `COORDENADOR` | dashboard, aptos a renovar, refinanciados, importacao, associados globais, usuarios |
| `TESOUREIRO` | novos contratos, confirmacoes, renovacoes, baixa manual, liquidacoes, devolucoes, despesas |

## Dados-Base Recomendados

Para conseguir percorrer o fluxo inteiro sem parar no meio, preparar ao menos:

- 1 associado novo ainda nao efetivado
- 1 associado em analise
- 1 associado ativo com contrato e ciclos materializados
- 1 associado apto a renovar
- 1 renovacao em analise
- 1 renovacao aprovada pela analise e aguardando coordenacao
- 1 renovacao aprovada pela coordenacao e aguardando tesouraria
- 1 contrato com parcela para baixa manual
- 1 contrato elegivel para liquidacao
- 1 devolucao ja registrada
- 1 despesa ja registrada
- 1 importacao de arquivo retorno concluida e outra com pendencia manual

## Convencoes de Validacao

Usar sempre este padrao em cada bloco:

- `Pre-condicao`: o que precisa existir antes de abrir a rota
- `Rota`: URL a ser testada
- `Acao manual`: passos concretos na interface
- `Resultado esperado`: o que deve acontecer
- `Observacoes/regressoes`: o que observar para nao deixar regressao passar

Quando uma rota for protegida:

- testar com o papel autorizado
- testar com um papel nao autorizado
- confirmar se o comportamento foi:
  - ocultacao no menu
  - redirecionamento para rota padrao do papel
  - ou bloqueio funcional coerente

## Fase 0 - Autenticacao e Guards

### 0.1 Acesso raiz

- [ ] Pre-condicao: navegador sem sessao ativa
- [ ] Rota: `/`
- [ ] Acao manual: abrir a aplicacao sem cookie/token
- [ ] Resultado esperado: redirecionar para `/login`
- [ ] Observacoes/regressoes: nao deve abrir dashboard sem autenticacao

### 0.2 Login valido

- [ ] Pre-condicao: usuario de teste valido
- [ ] Rota: `/login`
- [ ] Acao manual: autenticar com cada papel em sessao separada
- [ ] Resultado esperado:
  - `ADMIN` vai para `/dashboard`
  - `AGENTE` vai para `/agentes/meus-contratos`
  - `ANALISTA` vai para `/analise`
  - `COORDENADOR` vai para `/coordenacao/refinanciamento`
  - `TESOUREIRO` vai para `/tesouraria`
- [ ] Observacoes/regressoes: o redirect pos-login deve respeitar o papel principal

### 0.3 Login invalido

- [ ] Pre-condicao: credencial invalida
- [ ] Rota: `/login`
- [ ] Acao manual: informar senha errada
- [ ] Resultado esperado: erro visivel e usuario mantido na tela de login
- [ ] Observacoes/regressoes: nao deve gravar sessao parcial

### 0.4 Guard de rota protegida sem sessao

- [ ] Pre-condicao: sem sessao
- [ ] Rota: abrir diretamente `/associados`, `/dashboard` e `/tesouraria`
- [ ] Acao manual: colar as URLs no navegador
- [ ] Resultado esperado: redirecionar para `/login?next=...`
- [ ] Observacoes/regressoes: depois do login, o retorno deve abrir a rota originalmente pedida quando o papel tiver acesso

### 0.5 Guard de rota protegida com papel incorreto

- [ ] Pre-condicao: sessao ativa com papel nao autorizado
- [ ] Rota: testar exemplos como `/relatorios`, `/importacao`, `/tesouraria/despesas`, `/coordenacao/refinanciamento`
- [ ] Acao manual: abrir URL manualmente
- [ ] Resultado esperado: redirecionamento para a rota padrao do papel ou bloqueio coerente do guard
- [ ] Observacoes/regressoes: o menu tambem nao deve exibir a rota indevida

### 0.6 Logout e expiracao visual da sessao

- [ ] Pre-condicao: usuario logado
- [ ] Rota: header da aplicacao
- [ ] Acao manual: sair da conta e tentar voltar usando botao do navegador
- [ ] Resultado esperado: sessao encerrada e protecao reaplicada
- [ ] Observacoes/regressoes: nao pode reaproveitar tela protegida sem nova autenticacao

## Fase 1 - Agente

### 1.1 Meus Contratos

- [ ] Pre-condicao: login com `AGENTE`
- [ ] Rota: `/agentes/meus-contratos`
- [ ] Acao manual: validar cards, filtros, busca, tabela e badges
- [ ] Resultado esperado: listar apenas contratos/cadastros do proprio agente
- [ ] Observacoes/regressoes: busca, status e contadores devem bater com os dados carregados

### 1.2 Cadastrar Associado

- [ ] Pre-condicao: agente logado
- [ ] Rota: `/agentes/cadastrar-associado`
- [ ] Acao manual: percorrer o formulario completo, inclusive validacoes, mascara e anexos necessarios
- [ ] Resultado esperado: cadastro concluido com sucesso e associado entrando no fluxo seguinte
- [ ] Observacoes/regressoes:
  - validar etapas do formulario
  - validar salvamento de dados pessoais, endereco, banco, contato e documentos
  - confirmar se o novo associado aparece na esteira/lista esperada

### 1.3 Esteira de Pendencias

- [ ] Pre-condicao: agente com associados em analise, correcao ou pendencia
- [ ] Rota: `/agentes/esteira-pendencias`
- [ ] Acao manual: abrir a lista, filtrar, inspecionar pendencias, responder correcao quando aplicavel
- [ ] Resultado esperado: o agente enxerga apenas suas pendencias
- [ ] Observacoes/regressoes: cada acao deve refletir na etapa seguinte sem quebrar o historico

### 1.4 Refinanciados do Agente

- [ ] Pre-condicao: agente com contrato apto a renovar e outro ja em fluxo
- [ ] Rota: `/agentes/refinanciados`
- [ ] Acao manual:
  - localizar contrato apto
  - anexar termo de antecipacao
  - enviar para analise
- [ ] Resultado esperado:
  - item sai da lista bruta de aptos
  - passa para status operacional de renovacao em analise
- [ ] Observacoes/regressoes:
  - termo deve ser obrigatorio
  - fluxo deve seguir para o analista, nao direto para tesouraria

### 1.5 Meus Pagamentos

- [ ] Pre-condicao: agente com pagamentos gerados
- [ ] Rota: `/agentes/pagamentos`
- [ ] Acao manual: validar filtros, cards, historico e links/arquivos disponiveis
- [ ] Resultado esperado: exibir apenas pagamentos do proprio agente
- [ ] Observacoes/regressoes: conferir formatacao monetaria, datas e status

### 1.6 Fluxo transversal do agente para a analise

- [ ] Pre-condicao: cadastro novo criado pelo agente
- [ ] Rota: combinacao de `/agentes/cadastrar-associado`, `/agentes/meus-contratos` e `/agentes/esteira-pendencias`
- [ ] Acao manual: concluir um cadastro novo e acompanhar seu aparecimento na etapa seguinte
- [ ] Resultado esperado: o associado/contrato deve ficar visivel para a analise, sem ficar preso na origem
- [ ] Observacoes/regressoes: registrar qualquer quebra entre criacao, esteira e analise

## Fase 2 - Rotas Compartilhadas de Associados

### 2.1 Lista de Associados

- [ ] Pre-condicao: login com `ADMIN` e depois com `COORDENADOR`
- [ ] Rota: `/associados`
- [ ] Acao manual: validar cards, busca, filtros, tabela, detalhe e acoes laterais
- [ ] Resultado esperado:
  - `ADMIN` ve a lista completa
  - `COORDENADOR` ve a lista completa em modo leitura
- [ ] Observacoes/regressoes: esta rota nao deve aparecer para analista, tesoureiro ou agente

### 2.2 Detalhe do Associado

- [ ] Pre-condicao: existe associado com contratos, ciclos e documentos
- [ ] Rota: `/associados/[id]`
- [ ] Acao manual:
  - abrir por `ADMIN`
  - abrir por `COORDENADOR`
  - abrir por `ANALISTA`
  - abrir por `AGENTE` em associado permitido
- [ ] Resultado esperado:
  - detalhe carrega dados cadastrais, contratos, ciclos, parcelas e historicos
  - admin ve botoes extras como `Editar cadastro` e editor admin
- [ ] Observacoes/regressoes:
  - o detalhe deve abrir sem 404
  - validar dialogo de parcela
  - validar cards e anexos vinculados ao contrato

### 2.3 Editar Associado

- [ ] Pre-condicao: login com `ADMIN`
- [ ] Rota: `/associados/[id]/editar`
- [ ] Acao manual: abrir pelo lapis da lista e pelo botao do detalhe; editar campos e salvar
- [ ] Resultado esperado: abrir o formulario de cadastro em modo edicao, nao o detalhe
- [ ] Observacoes/regressoes:
  - o lapis da lista deve apontar para esta rota
  - o botao `Editar cadastro` no detalhe deve continuar existindo
  - mascaras e validacoes do formulario devem permanecer corretas

### 2.4 Novo Associado pelo caminho administrativo

- [ ] Pre-condicao: login com `ADMIN`
- [ ] Rota: `/associados/novo`
- [ ] Acao manual: abrir a rota diretamente e validar o formulario em modo criacao
- [ ] Resultado esperado: tela acessivel apenas ao admin
- [ ] Observacoes/regressoes: esta rota nao fica no menu principal, mas precisa continuar funcional

## Fase 3 - Analista

### 3.1 Dashboard de Analise

- [ ] Pre-condicao: login com `ANALISTA`
- [ ] Rota: `/analise`
- [ ] Acao manual: validar KPIs, filas, filtros e cards/resumos
- [ ] Resultado esperado: a fila deve refletir os cadastros/itens de analise disponiveis
- [ ] Observacoes/regressoes: conferir consistencia com a esteira do agente

### 3.2 Contratos para Renovacao

- [ ] Pre-condicao: existe renovacao enviada por agente
- [ ] Rota: `/analise/aptos`
- [ ] Acao manual:
  - abrir item vindo do agente
  - assumir a analise, quando aplicavel
  - aprovar sem reenviar termo
- [ ] Resultado esperado:
  - item muda para a etapa pos-analise
  - deve seguir para coordenacao, nao para tesouraria
- [ ] Observacoes/regressoes:
  - termo anexado pelo agente deve estar visivel
  - o analista nao deve ser obrigado a subir novo termo por padrao

### 3.3 Fluxo transversal da analise para a coordenacao

- [ ] Pre-condicao: renovacao em `em_analise_renovacao`
- [ ] Rota: `/analise/aptos` + `/coordenacao/refinanciamento`
- [ ] Acao manual: aprovar no analista e entrar depois como coordenador
- [ ] Resultado esperado: o mesmo item deve aparecer na coordenacao como aguardando validacao
- [ ] Observacoes/regressoes: qualquer salto direto para tesouraria e bug

## Fase 4 - Coordenacao

### 4.1 Dashboard Executivo

- [ ] Pre-condicao: login com `COORDENADOR`
- [ ] Rota: `/dashboard`
- [ ] Acao manual:
  - validar acesso
  - abrir filtros avancados de todas as secoes
  - testar filtro por dia, agente e status do associado
- [ ] Resultado esperado:
  - coordenador acessa o dashboard normalmente
  - filtros aparecem nas secoes previstas
- [ ] Observacoes/regressoes:
  - nao deve haver elementos pretos ilegiveis nos graficos
  - cards e charts precisam reagir aos filtros

### 4.2 Aptos a Renovar

- [ ] Pre-condicao: existe renovacao aprovada pelo analista
- [ ] Rota: `/coordenacao/refinanciamento`
- [ ] Acao manual:
  - validar anexos
  - aprovar e enviar para tesouraria
  - testar caminho de desativacao via liquidacao
- [ ] Resultado esperado:
  - a coordenacao ve apenas itens pos-analise
  - aprovacao envia para `Tesouraria > Renovacoes de Ciclo`
  - desativacao redireciona para liquidacao
- [ ] Observacoes/regressoes:
  - esta tela nao deve listar aptos brutos do agente
  - conferir query params ao entrar em liquidacoes

### 4.3 Refinanciados da Coordenacao

- [ ] Pre-condicao: existem renovacoes em historico
- [ ] Rota: `/coordenacao/refinanciados`
- [ ] Acao manual: validar listagem, filtros, statuses e historico
- [ ] Resultado esperado: coordenacao acompanha os itens refinanciados/historicos
- [ ] Observacoes/regressoes: verificar coerencia com tesouraria e com a origem da renovacao

### 4.4 Importacao / Arquivo Retorno

- [ ] Pre-condicao: coordenador logado e arquivo `.txt` de teste disponivel
- [ ] Rota: `/importacao`
- [ ] Acao manual:
  - validar cards, historico e abas
  - fazer upload de arquivo valido
  - consultar detalhe da ultima importacao
  - testar reprocessamento
- [ ] Resultado esperado: coordenador tem acesso integral ao modulo
- [ ] Observacoes/regressoes:
  - tesoureiro nao deve mais acessar essa rota
  - usar `docs/QA_SEMANA_4.md` como roteiro complementar de profundidade

### 4.5 Leitura global de associados

- [ ] Pre-condicao: coordenador logado
- [ ] Rota: `/associados` e `/associados/[id]`
- [ ] Acao manual: abrir associados de agentes diferentes
- [ ] Resultado esperado: coordenador consegue leitura global
- [ ] Observacoes/regressoes: nao deve haver acesso a `/associados/[id]/editar`

### 4.6 Gestao de Usuarios para Coordenacao

- [ ] Pre-condicao: coordenador logado
- [ ] Rota: `/configuracoes/usuarios`
- [ ] Acao manual:
  - listar usuarios
  - criar `AGENTE`, `ANALISTA` e `TESOUREIRO`
  - editar acessos permitidos
  - resetar senha
- [ ] Resultado esperado:
  - coordenador enxerga apenas usuarios operacionais permitidos
  - nao consegue criar/editar `ADMIN` ou `COORDENADOR`
- [ ] Observacoes/regressoes:
  - a propria conta do coordenador nao deve permitir autoalteracao indevida

## Fase 5 - Tesouraria

### 5.1 Novos Contratos

- [ ] Pre-condicao: login com `TESOUREIRO` e existencia de contratos pendentes
- [ ] Rota: `/tesouraria`
- [ ] Acao manual:
  - validar cards, busca e tabela
  - conferir colunas `Matricula`, `Valor Aux. Liberado / Comissao`, percentual de repasse e anexos compactos
  - subir comprovantes obrigatorios
  - efetivar contrato
- [ ] Resultado esperado:
  - fluxo de novos contratos continua funcional
  - apos efetivacao, o item sai da fila correta
- [ ] Observacoes/regressoes:
  - anexos ficam ao final da linha
  - botao de efetivar deve exigir os arquivos necessarios

### 5.2 Confirmacoes

- [ ] Pre-condicao: contrato aguardando confirmacao
- [ ] Rota: `/tesouraria/confirmacoes`
- [ ] Acao manual: validar filtros, tabela, confirmacao de ligacao/averbacao e estados finais
- [ ] Resultado esperado: as confirmacoes atualizam a situacao do contrato
- [ ] Observacoes/regressoes: checar consistencia com o detalhe do associado

### 5.3 Renovacoes de Ciclo

- [ ] Pre-condicao: renovacao aprovada pela coordenacao
- [ ] Rota: `/tesouraria/refinanciamentos`
- [ ] Acao manual:
  - localizar a renovacao
  - anexar comprovantes finais
  - efetivar
- [ ] Resultado esperado: somente itens validados pela coordenacao entram aqui
- [ ] Observacoes/regressoes:
  - fluxo de contrato novo nao deve aparecer misturado
  - efetivacao deve materializar o proximo ciclo corretamente

### 5.4 Baixa Manual

- [ ] Pre-condicao: contrato/parcela pendente de baixa manual
- [ ] Rota: `/tesouraria/baixa-manual`
- [ ] Acao manual:
  - localizar contrato/parcela
  - validar filtros
  - efetuar baixa manual
- [ ] Resultado esperado: a parcela muda de estado sem afetar itens indevidos
- [ ] Observacoes/regressoes:
  - parcelas `liquidada` nao devem aparecer como pendentes
  - coordenador tambem deve ter acesso a esta rota

### 5.5 Liquidacoes

- [ ] Pre-condicao: contrato elegivel para encerramento por liquidacao
- [ ] Rota: `/tesouraria/liquidacoes`
- [ ] Acao manual:
  - validar abas `Elegiveis` e `Liquidados`
  - registrar liquidacao com comprovante, data, valor e observacao
  - testar reversao com `ADMIN`
- [ ] Resultado esperado:
  - parcelas elegiveis passam para `liquidada`
  - contrato fica `encerrado`
  - associado pode virar `inativo` quando for o ultimo contrato
- [ ] Observacoes/regressoes:
  - nenhum ciclo novo deve ser aberto apos a liquidacao
  - coordenacao deve conseguir abrir a tela por atalho de desativacao

### 5.6 Devolucoes ao Associado

- [ ] Pre-condicao: existe contrato elegivel e historico de devolucao
- [ ] Rota: `/tesouraria/devolucoes`
- [ ] Acao manual:
  - aba `Registrar`: criar devolucao de `pagamento indevido`
  - criar devolucao de `desconto indevido`
  - validar competencia, quantidade de parcelas e upload de anexos
  - aba `Historico`: filtrar e reverter com `ADMIN`
- [ ] Resultado esperado:
  - registro nao altera parcela, ciclo ou liquidacao
  - historico mostra status `registrada`/`revertida`
- [ ] Observacoes/regressoes:
  - `COORDENADOR`, `TESOUREIRO` e `ADMIN` podem registrar
  - somente `ADMIN` pode reverter

### 5.7 Despesas

- [ ] Pre-condicao: existem despesas cadastradas ou dados para cadastrar
- [ ] Rota: `/tesouraria/despesas`
- [ ] Acao manual: validar cards, tabela, filtros, cadastro/edicao se disponivel e reflexo no dashboard
- [ ] Resultado esperado: despesas ficam visiveis e coerentes com a secao financeira
- [ ] Observacoes/regressoes: essa rota continua restrita a `TESOUREIRO` e `ADMIN`

### 5.8 Renovacao de Ciclos

- [ ] Pre-condicao: existe importacao concluida e/ou renovacao automatica materializada
- [ ] Rota: `/renovacao-ciclos`
- [ ] Acao manual:
  - abrir a tela como `TESOUREIRO`
  - trocar competencia
  - validar cards e detalhamento por item
- [ ] Resultado esperado: a tela consolida a leitura operacional da renovacao por competencia
- [ ] Observacoes/regressoes:
  - `ADMIN` tambem deve conseguir acessar
  - papeis nao autorizados nao devem ver essa rota no menu

### 5.9 Fluxo transversal da tesouraria

- [ ] Pre-condicao: um contrato novo, uma renovacao, uma baixa manual, uma liquidacao e uma devolucao disponiveis
- [ ] Rota: combinacao das rotas acima
- [ ] Acao manual: percorrer os cinco submodulos em ordem e abrir depois o detalhe do associado
- [ ] Resultado esperado: o detalhe do associado deve refletir corretamente o que a tesouraria fez
- [ ] Observacoes/regressoes:
  - historicos devem ficar consistentes
  - anexos/comprovantes precisam aparecer nos blocos corretos

## Fase 6 - Admin

### 6.1 Dashboard Executivo do Admin

- [ ] Pre-condicao: login com `ADMIN`
- [ ] Rota: `/dashboard`
- [ ] Acao manual:
  - validar as quatro secoes
  - usar filtros por dia, agente e status do associado
  - abrir detalhes exportaveis
- [ ] Resultado esperado: admin ve o dashboard completo
- [ ] Observacoes/regressoes:
  - conferir KPIs de tesouraria, inclusive receita liquida e despesas
  - conferir charts/ranking por agente sem elementos pretos ilegiveis

### 6.2 Gestao de Usuarios

- [ ] Pre-condicao: admin logado
- [ ] Rota: `/configuracoes/usuarios`
- [ ] Acao manual:
  - listar todos os usuarios internos
  - criar usuarios por papel
  - editar acessos
  - ativar/desativar
  - resetar senha
- [ ] Resultado esperado: admin tem controle completo dos usuarios internos previstos
- [ ] Observacoes/regressoes:
  - preservar protecao de auto-bloqueio e auto-despromocao
  - conferir filtros, busca e cards

### 6.3 Importacao como Admin

- [ ] Pre-condicao: admin logado
- [ ] Rota: `/importacao`
- [ ] Acao manual: repetir pelo menos um fluxo basico de upload e historico
- [ ] Resultado esperado: o admin tem o mesmo acesso funcional que a coordenacao
- [ ] Observacoes/regressoes: validar que a tesouraria continua sem acesso

### 6.4 Editor Admin no Detalhe do Associado

- [ ] Pre-condicao: associado com contrato, ciclos, parcelas, renovacao e arquivos
- [ ] Rota: `/associados/[id]`
- [ ] Acao manual:
  - abrir detalhe
  - ativar `Modo edicao admin`
  - abrir `Editar cadastro`
  - abrir o editor admin do contrato
- [ ] Resultado esperado:
  - o detalhe continua tendo o botao `Editar cadastro`
  - o editor admin funciona como superficie separada para overrides operacionais
- [ ] Observacoes/regressoes:
  - o lapis da lista deve abrir `/associados/[id]/editar`
  - o editor admin nao deve sequestrar a edicao cadastral tradicional

### 6.5 Overrides de Contrato, Ciclos e Parcelas

- [ ] Pre-condicao: admin em modo edicao e associado com mais de um ciclo
- [ ] Rota: `/associados/[id]`
- [ ] Acao manual:
  - editar dados do contrato
  - alterar datas e valores
  - mover meses entre ciclos
  - criar/remover ciclo
  - criar/remover parcela
  - anexar comprovantes nos ciclos
- [ ] Resultado esperado:
  - alteracoes gravam no banco imediatamente apos confirmacao
  - layout manual permanece refletido no detalhe
- [ ] Observacoes/regressoes:
  - calendarios devem usar componentes estilizados do projeto
  - uploads e comprovantes por ciclo devem estar disponiveis
  - validar tooltips nos inputs do editor admin

### 6.6 Documentos, Comprovantes e Historico Administrativo

- [ ] Pre-condicao: admin em modo edicao e arquivos existentes
- [ ] Rota: `/associados/[id]`
- [ ] Acao manual:
  - substituir documento/comprovante
  - alterar status de validacao
  - abrir historico administrativo
  - reverter operacao elegivel
- [ ] Resultado esperado:
  - versao anterior do arquivo continua no historico
  - historico registra ator, motivo, data/hora e diff
- [ ] Observacoes/regressoes:
  - reversao deve criar novo evento, nao apagar o antigo

### 6.7 Relatorios

- [ ] Pre-condicao: admin logado
- [ ] Rota: `/relatorios`
- [ ] Acao manual: abrir a tela, validar filtros/exportacoes/cards/tabelas existentes
- [ ] Resultado esperado: modulo acessivel apenas ao admin
- [ ] Observacoes/regressoes: papeis nao autorizados nao devem ver essa rota no menu

## Smoke de Alias Legados

### Alias `/pagamentos`

- [ ] Pre-condicao: sessao ativa com `AGENTE`, depois com `TESOUREIRO`, depois com `ADMIN`
- [ ] Rota: `/pagamentos`
- [ ] Acao manual: abrir a rota diretamente
- [ ] Resultado esperado:
  - `AGENTE`, `TESOUREIRO` e `ADMIN` redirecionam para `/agentes/pagamentos`
  - outros papeis redirecionam para sua rota padrao
- [ ] Observacoes/regressoes: o alias existe apenas como compatibilidade

### Alias `/renovacoes`

- [ ] Pre-condicao: testar com `AGENTE`, `COORDENADOR`, `TESOUREIRO` e `ADMIN`
- [ ] Rota: `/renovacoes`
- [ ] Acao manual: abrir a rota diretamente
- [ ] Resultado esperado:
  - `AGENTE` -> `/agentes/refinanciados`
  - `COORDENADOR` -> `/coordenacao/refinanciamento`
  - `TESOUREIRO` -> `/renovacao-ciclos`
  - `ADMIN` -> `/renovacao-ciclos`
- [ ] Observacoes/regressoes: nenhum alias deve ficar em loop ou gerar 404

## Apendice A - Inventario de Rotas Web e Cobertura

Este inventario considera apenas paginas do App Router. `route.ts` de proxy/API ficam fora do escopo de QA manual de navegacao.

| Rota | Cobertura principal neste checklist |
| --- | --- |
| `/` | Fase 0 |
| `/login` | Fase 0 |
| `/dashboard` | Fase 4 e Fase 6 |
| `/agentes/meus-contratos` | Fase 1 |
| `/agentes/cadastrar-associado` | Fase 1 |
| `/agentes/esteira-pendencias` | Fase 1 |
| `/agentes/refinanciados` | Fase 1 |
| `/agentes/pagamentos` | Fase 1 |
| `/analise` | Fase 3 |
| `/analise/aptos` | Fase 3 |
| `/coordenacao/refinanciamento` | Fase 4 |
| `/coordenacao/refinanciados` | Fase 4 |
| `/associados` | Fase 2 e Fase 4 |
| `/associados/novo` | Fase 2 |
| `/associados/[id]` | Fase 2 e Fase 6 |
| `/associados/[id]/editar` | Fase 2 |
| `/tesouraria` | Fase 5 |
| `/tesouraria/confirmacoes` | Fase 5 |
| `/tesouraria/refinanciamentos` | Fase 5 |
| `/tesouraria/baixa-manual` | Fase 5 |
| `/tesouraria/liquidacoes` | Fase 5 |
| `/tesouraria/devolucoes` | Fase 5 |
| `/tesouraria/despesas` | Fase 5 |
| `/importacao` | Fase 4 e Fase 6 |
| `/renovacao-ciclos` | Fase 5 |
| `/relatorios` | Fase 6 |
| `/configuracoes/usuarios` | Fase 4 e Fase 6 |
| `/pagamentos` | Smoke de alias legado |
| `/renovacoes` | Smoke de alias legado |

## Apendice B - Matriz Simples de Permissao Manual

Usar esta matriz como referencia rapida de visibilidade/acesso.

| Rota/modulo | ADMIN | AGENTE | ANALISTA | COORDENADOR | TESOUREIRO |
| --- | --- | --- | --- | --- | --- |
| `/dashboard` | sim | nao | nao | sim | nao |
| `/agentes/meus-contratos` | sim | sim | nao | nao | nao |
| `/agentes/cadastrar-associado` | nao | sim | nao | nao | nao |
| `/agentes/esteira-pendencias` | sim | sim | nao | nao | nao |
| `/agentes/refinanciados` | sim | sim | nao | nao | nao |
| `/agentes/pagamentos` | sim | sim | nao | nao | sim |
| `/analise` | sim | nao | sim | nao | nao |
| `/analise/aptos` | sim | nao | sim | nao | nao |
| `/coordenacao/refinanciamento` | sim | nao | nao | sim | nao |
| `/coordenacao/refinanciados` | sim | nao | nao | sim | nao |
| `/associados` | sim | nao | nao | sim | nao |
| `/associados/[id]` | sim | sim restrito | sim | sim | nao |
| `/associados/[id]/editar` | sim | nao | nao | nao | nao |
| `/associados/novo` | sim | nao | nao | nao | nao |
| `/tesouraria` | sim | nao | nao | nao | sim |
| `/tesouraria/confirmacoes` | sim | nao | nao | nao | sim |
| `/tesouraria/refinanciamentos` | sim | nao | nao | nao | sim |
| `/tesouraria/baixa-manual` | sim | nao | nao | sim | sim |
| `/tesouraria/liquidacoes` | sim | nao | nao | sim | sim |
| `/tesouraria/devolucoes` | sim | nao | nao | sim | sim |
| `/tesouraria/despesas` | sim | nao | nao | nao | sim |
| `/importacao` | sim | nao | nao | sim | nao |
| `/renovacao-ciclos` | sim | nao | nao | nao | sim |
| `/relatorios` | sim | nao | nao | nao | nao |
| `/configuracoes/usuarios` | sim | nao | nao | sim | nao |

## Fechamento da Execucao

Ao final da rodada manual:

- registrar bugs encontrados por rota
- separar bugs por gravidade:
  - bloqueante
  - funcional
  - permissao/seguranca
  - UX/visual
- anotar:
  - papel usado
  - massa de dados usada
  - se o problema foi intermitente ou reproduzivel
  - prints e IDs dos registros afetados

Se esta rodada envolver importacao, liquidacao, devolucao ou editor admin, anexar no relatorio final os IDs dos contratos/associados usados para facilitar reproducao.
