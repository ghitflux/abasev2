# Checklist de Validacao Manual das Melhorias Web

Atualizado em: 08/04/2026

## Objetivo

Validar manualmente os ajustes prioritarios da rodada atual, com foco em:

1. Admin Editor
2. Tesouraria e pagamentos
3. Associados, contratos, importacao e dashboard de ciclos
4. Coordenacao e Aptos a renovar

Este documento deve ser usado como roteiro unico de homologacao funcional.

## Como executar

- Validar por perfil real de uso: `ADMIN`, `COORDENADOR`, `TESOUREIRO`, `ANALISTA` e `AGENTE`.
- Registrar evidencia de cada falha com print, rota, perfil usado e horario.
- Sempre testar o fluxo feliz e a regressao principal do bloco.
- Ao encontrar falha, anotar:
  - rota
  - perfil
  - passo executado
  - resultado atual
  - resultado esperado

## Massa minima recomendada

- 1 associado ativo com contrato e ciclos materializados.
- 1 associado com parcelas nao descontadas.
- 1 contrato apto a renovar.
- 1 renovacao em analise.
- 1 renovacao aprovada para tesouraria.
- 1 contrato com comprovantes de efetivacao.
- 1 contrato com baixa manual.
- 1 contrato elegivel para liquidacao.
- 1 devolucao registrada.
- 1 despesa manual registrada.
- 1 arquivo retorno com valores normais e 1 com ocorrencias de `30/50`.

## Criterio geral de pronto

- [ ] Nenhum fluxo principal trava por erro de tela, erro de API ou salvamento parcial.
- [ ] Labels, sidebar e nomenclaturas refletem a rotina real de cada perfil.
- [ ] O detalhe do associado, a tesouraria e o historico de renovacao permanecem coerentes entre si.
- [ ] Toda acao critica com alteracao operacional ou financeira deixa rastreio visivel.

## 1. Admin Editor

### 1.1 Acesso e permissao

- [ ] `ADMIN` acessa [associados/[id]](/mnt/d/apps/abasev2/abasev2/apps/web/src/app/(dashboard)/associados/[id]/page.tsx) e consegue ativar o `Modo editor avancado`.
- [ ] `COORDENADOR` acessa o mesmo detalhe do associado e tambem consegue ativar o editor.
- [ ] `AGENTE`, `ANALISTA` e `TESOUREIRO` nao recebem acesso indevido ao editor.
- [ ] O label da interface nao exibe mais o texto antigo de `modo admin` onde o fluxo agora deve aparecer como editor avancado.

### 1.2 Salvamento de dados do contrato

- [ ] Alterar um campo simples do contrato e salvar. Esperado: persistir ao recarregar.
- [ ] Alterar dados de contrato e esteira no mesmo `save-all`. Esperado: ambos persistem juntos.
- [ ] Salvar sem alteracoes. Esperado: nao criar comportamento incorreto nem erro de conflito.
- [ ] Forcar conflito de versao com dois usuarios na mesma tela. Esperado: o segundo usuario recebe bloqueio coerente.

### 1.3 Ciclos e parcelas

- [ ] Editar apenas um ciclo existente. Esperado: o ajuste persiste apos recarregar.
- [ ] Alterar datas de inicio/fim do ciclo. Esperado: a mudanca aparece no detalhe e nao quebra a estrutura do contrato.
- [ ] Definir o status do ciclo como `pendencia`. Esperado: salvar com sucesso e exibir badge coerente.
- [ ] Remover uma parcela de um ciclo sem quebrar o contrato. Esperado: o contrato continua consistente.
- [ ] Deixar um ciclo com parcela nao descontada fora do ciclo. Esperado: o ciclo pode ficar em `pendencia`.
- [ ] Reordenar parcelas entre ciclos. Esperado: referencias e numeracao permanecem coerentes.
- [ ] Reabrir o detalhe do associado apos salvar. Esperado: o layout manual continua igual ao que foi salvo.

### 1.4 Warnings de sobreposicao

- [ ] Criar dois ciclos com datas sobrepostas. Esperado: o editor avisa antes de salvar.
- [ ] Salvar mesmo com sobreposicao confirmada. Esperado: o save conclui e o retorno da tela continua trazendo warnings.
- [ ] Criar duas parcelas com a mesma competencia em ciclos diferentes. Esperado: o sistema avisa a duplicidade.

### 1.5 Anexos e auditoria

- [ ] Anexar comprovantes em um ciclo pelo editor. Esperado: o upload conclui e os arquivos aparecem no detalhe do ciclo.
- [ ] Verificar o historico do editor. Esperado: existe registro com ator, motivo e timestamp.
- [ ] Versionar arquivo/comprovante pelo editor. Esperado: nova versao fica visivel sem apagar o historico anterior.
- [ ] Confirmar que o anexo operacional enviado pelo editor aparece depois em `Tesouraria > Pagamentos`.

### 1.6 Regressao operacional

- [ ] Repetir um caso real semelhante ao do associado `Justino`, com ajuste de ciclo e salvamento completo.
- [ ] Esperado: nenhuma edicao de ciclo fica sem persistencia e nenhum ciclo some, zera ou fica inativo sem motivo.

## 2. Tesouraria e Pagamentos

### 2.1 Novos Contratos

- [ ] Abrir `/tesouraria` com perfil `TESOUREIRO`. Esperado: listar apenas contratos realmente novos ou novos pendentes de pagamento.
- [ ] Confirmar que contratos ja pagos com comprovantes nao ficam aparecendo indevidamente como pendentes.
- [ ] Abrir detalhes de um contrato novo. Esperado: dados do associado, contrato e anexos batem com o cadastro.
- [ ] Validar dropdown de exportacao da rota. Esperado: existir `Relatorio do dia` e `Relatorio do mes` em `PDF` e `XLS`.
- [ ] Validar exportacao do dia em `/tesouraria`. Esperado: o arquivo baixa sem erro e respeita o recorte operacional do dia.
- [ ] Validar exportacao do mes em `/tesouraria`. Esperado: o arquivo baixa sem erro e respeita o recorte operacional do mes.

### 2.2 Pagamentos

- [ ] Abrir `/tesouraria/pagamentos`. Esperado: a pagina carrega sem erro vermelho de requisicao.
- [ ] Validar cards, tabela, filtros e exportacao. Esperado: a listagem usa a rota propria da tesouraria.
- [ ] Confirmar que evidencias de pagamento aparecem corretamente.
- [ ] Confirmar que evidencias enviadas pelo editor aparecem com origem operacional do editor.
- [ ] Validar um contrato pago e outro pendente. Esperado: status, valor e anexos batem com o retorno da API.
- [ ] Validar dropdown de exportacao da rota. Esperado: existir `Relatorio do dia` e `Relatorio do mes` em `PDF` e `XLS`.
- [ ] Validar exportacao do dia em `/tesouraria/pagamentos`.
- [ ] Validar exportacao do mes em `/tesouraria/pagamentos`.

### 2.3 Contratos para Renovacao

- [ ] Abrir `/tesouraria/refinanciamentos`. Esperado: titulo e secoes com nomenclatura `Contratos para Renovacao`.
- [ ] Validar contrato pendente para pagamento da renovacao. Esperado: mostrar anexos existentes e acao correta da tesouraria.
- [ ] Verificar se existe campo/acao para anexo do pagamento do agente. Esperado: a tesouraria consegue anexar o comprovante do agente.
- [ ] Validar coluna `Valor / Repasse`. Esperado: valor do associado usa o disponivel operacional e o repasse do agente permanece correto.
- [ ] Validar dropdown de exportacao da rota. Esperado: existir `Relatorio do dia` e `Relatorio do mes` em `PDF` e `XLS`.
- [ ] Validar exportacao do dia em `/tesouraria/refinanciamentos`.
- [ ] Validar exportacao do mes em `/tesouraria/refinanciamentos`.

### 2.4 Inadimplentes

- [ ] Abrir `/tesouraria/baixa-manual`. Esperado: listar parcelas nao pagas de meses diferentes, nao apenas um mes fixo.
- [ ] Validar busca por associado, CPF e contrato. Esperado: encontrar registros fora de `03/2026`.
- [ ] Confirmar ausencia de calendario duplicado fora dos filtros avancados.
- [ ] Validar dropdown de exportacao da rota. Esperado: existir `Relatorio do dia` e `Relatorio do mes` em `PDF` e `XLS`.
- [ ] Validar exportacao do dia em `/tesouraria/baixa-manual`.
- [ ] Validar exportacao do mes em `/tesouraria/baixa-manual`.

### 2.5 Liquidacao

- [ ] Abrir `/tesouraria/liquidacoes`. Esperado: carregamento aceitavel, sem registros vazios dominando a lista.
- [ ] Validar se a listagem principal nao traz associados sem parcela elegivel.
- [ ] Validar abertura de detalhe do associado a partir da tela. Esperado: nao precisar sair da rota para consultar o cadastro.
- [ ] Validar liquidacao de um contrato elegivel. Esperado: status, historico e efeitos financeiros refletidos corretamente.
- [ ] Validar a acao de liquidacao manual, se disponivel na tela.
- [ ] Validar dropdown de exportacao da rota. Esperado: existir `Relatorio do dia` e `Relatorio do mes` em `PDF` e `XLS`.
- [ ] Validar exportacao do dia em `/tesouraria/liquidacoes`.
- [ ] Validar exportacao do mes em `/tesouraria/liquidacoes`.

### 2.6 Devolucoes

- [ ] Abrir `/tesouraria/devolucoes`. Esperado: listagem, abas e KPIs carregam corretamente.
- [ ] Excluir uma devolucao de teste. Esperado: sai da lista e atualiza os indicadores.
- [ ] Validar KPI de duplicidades. Esperado: nao ficar zerado se houver base com duplicidade.
- [ ] Comparar aba de registrar liquidacao com pos-liquidacao. Esperado: elas nao devem se comportar como copias identicas.
- [ ] Validar dropdown de exportacao da rota. Esperado: existir `Relatorio do dia` e `Relatorio do mes` em `PDF` e `XLS`.
- [ ] Validar exportacao do dia em `/tesouraria/devolucoes`.
- [ ] Validar exportacao do mes em `/tesouraria/devolucoes`.

### 2.7 Despesas

- [ ] Abrir `/tesouraria/despesas`. Esperado: cards e detalhamento do mes carregam sem erro.
- [ ] Validar separacao entre `despesas manuais` e `despesas avulsas`.
- [ ] Confirmar se devolucoes aparecem dentro de `despesas avulsas`.
- [ ] Validar uma recorrencia cadastrada. Esperado: comportamento coerente no mes atual e no proximo ciclo esperado.
- [ ] Validar dropdown de exportacao da rota. Esperado: existir `Relatorio do dia` e `Relatorio do mes` em `PDF` e `XLS`.
- [ ] Validar exportacao do dia em `/tesouraria/despesas`.
- [ ] Validar exportacao do mes em `/tesouraria/despesas`.

## 3. Associados, Contratos, Importacao e Dashboard de Ciclos

### 3.1 Associados e contratos

- [ ] Validar filtros por mes em associados/contratos.
- [ ] Validar filtros por status ou legenda do arquivo retorno.
- [ ] Confirmar que a busca continua encontrando associados antigos, inclusive casos corrigidos pela importacao.

### 3.2 Importacao

- [ ] Abrir a tela de importacao e clicar nos cards numericos. Esperado: abrir a listagem filtrada correspondente.
- [ ] Validar navegacao entre cards de resumo e detalhes do arquivo.
- [ ] Validar se a listagem final do arquivo retorno mostra tambem o card de `Valores 30/50`.

### 3.3 Dashboard de Ciclos

- [ ] Abrir `/renovacao-ciclos`. Esperado: carregamento mais fluido.
- [ ] Confirmar remocao da secao `Monitoramento de ciclos (trimestral)`.
- [ ] Confirmar remocao dos cards `1/3`, `2/3` e `3/3`.
- [ ] Confirmar remocao do alerta `nao possuir parcelas conciliadas`, se ele nao fizer mais parte da tela.
- [ ] Validar os cards internos de cada mes. Esperado: contadores e valores coerentes com a base.

### 3.4 Casos 30/50

- [ ] Escolher um caso de `30/50` vindo de arquivo retorno e buscar o associado no sistema.
- [ ] Confirmar que o associado aparece na busca global e na rota de associados.
- [ ] Confirmar que o associado esta vinculado ao `Agente Padrao ABASE`.
- [ ] Confirmar existencia de ciclos e parcelas desde outubro, quando aplicavel ao caso.
- [ ] Tentar criar nova parcela em um caso antes problemático. Esperado: o sistema nao trava nem bloqueia sem motivo.

## 4. Coordenacao e Aptos a Renovar

### 4.1 Sidebar e nomenclatura

- [ ] Logar com `COORDENADOR` e abrir a sidebar.
- [ ] Confirmar que a secao de coordenacao esta separada da visao do analista.
- [ ] Confirmar ordem e nomes coerentes com a rotina da coordenacao.

### 4.2 Coordenacao de renovacao

- [ ] Abrir `/coordenacao/refinanciamento`. Esperado: tela principal de `Aptos a renovar`.
- [ ] Validar aprovacao individual. Esperado: item sai da fila correta e vai para o proximo estado esperado.
- [ ] Validar devolucao para analise. Esperado: registrar motivo e refletir no historico.
- [ ] Validar aprovacao em massa, se houver itens elegiveis.
- [ ] Validar visualizacao de anexos e detalhes sem inconsistencias de status.
- [ ] Validar encaminhamento para liquidacao quando o caso for de liquidacao, nao de renovacao.

### 4.3 Refinanciados

- [ ] Abrir `/coordenacao/refinanciados`. Esperado: historico carregado com status coerentes.
- [ ] Abrir modal de detalhes. Esperado: mostrar dados completos do associado, contrato, anexos e historico.
- [ ] Confirmar coerencia entre status da coordenacao e o que aparece depois na tesouraria.

### 4.4 Aptos a renovar por perfil

- [ ] Com `AGENTE`, `ANALISTA`, `COORDENADOR` e `ADMIN`, localizar a rota `/agentes/refinanciados`.
- [ ] Confirmar que a nomenclatura visivel agora e `Aptos a renovar`.
- [ ] Validar que o botao principal de envio continua funcionando.
- [ ] Se o botao `Cancelar renovacao` estiver disponivel, validar que exige motivo e executa a regra de desativacao.
- [ ] Validar modal de detalhes nessa frente. Esperado: comportamento equivalente ao modal usado na coordenacao.

## 5. Checklist transversal de coerencia

- [ ] Uma alteracao no editor do associado aparece corretamente na tesouraria quando o fluxo depende disso.
- [ ] Uma renovacao aprovada na coordenacao aparece corretamente na tesouraria.
- [ ] Um pagamento ou efetivacao refletido na tesouraria aparece corretamente no detalhe do associado.
- [ ] Um cancelamento, devolucao ou liquidacao nao deixa lixo visual em cards, filtros ou historicos.
- [ ] Nenhuma tela principal mostra nomenclatura antiga quando a regra atual pede `Aptos a renovar` ou `Contratos para Renovacao`.

## 6. Registro final da homologacao

Preencher ao concluir a rodada:

- Data da validacao:
- Responsavel:
- Ambiente:
- Blocos validados:
- Blocos reprovados:
- Bugs encontrados:
- Evidencias salvas em:
- Parecer final:
  - [ ] Aprovado
  - [ ] Aprovado com ressalvas
  - [ ] Reprovado para correcao
