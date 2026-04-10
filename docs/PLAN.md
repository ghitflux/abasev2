# Plano Revisado de Correção Imediata

## Resumo
- Este plano substitui o plano anterior e fica restrito aos 4 blocos que você listou.
- Ordem de execução: `1. Admin Editor`, `2. Tesouraria`, `3. Associados/Contratos + Importação + Dashboard de Ciclos`, `4. Coordenador + Aptos a renovar`.
- Objetivo da rodada: corrigir comportamento, nomenclatura, persistência e leitura operacional nessas frentes agora, sem abrir backlog paralelo.
- Definição de pronto geral: os fluxos passam a salvar e listar corretamente, os dados antigos inconsistentes são reconciliados, e a navegação reflete a rotina real de cada perfil.

## Mudanças principais e interfaces

### 1. Admin Editor
- Revisar integralmente o editor administrativo de associado, contrato, ciclos, parcelas, refinanciamento e anexos.
- Corrigir o fluxo de `save-all` e o ajuste isolado de ciclos para que qualquer edição de ciclo persista de forma confiável, inclusive o caso-regressão do associado `Justino`.
- Adicionar `pendencia` como status oficial de `Ciclo.Status` e refletir isso em backend, serializers, schema, filtros e badges.
- Permitir que parcela não descontada saia do ciclo sem quebrar o contrato; nesse cenário o ciclo pode ficar em `pendencia`.
- Detectar sobreposição de meses/datas/informações entre ciclos e parcelas no salvamento.
- A sobreposição não bloqueia o save; o sistema deve avisar claramente antes de confirmar e retornar o resumo dos conflitos após salvar.
- Remover nomenclaturas incorretas ou duplicadas no modo admin editor e padronizar os textos para operação financeira.
- Anexos lançados pelo admin editor para pagamentos devem ser registrados como pagamentos feitos via admin editor e aparecer em `Tesouraria > Pagamentos`.

### 2. Tesouraria
- `/tesouraria` deve listar apenas contratos realmente novos e contratos novos pendentes de pagamento.
- Fazer reconciliação dos contratos já pagos que ainda estão `pendente` apesar de já possuírem comprovantes de associado e agente.
- Em `Tesouraria > Renovações`, manter a URL atual e trocar labels/títulos para `Contratos para Renovação`.
- Nessa tela, adicionar o campo de anexo do pagamento do agente e manter os campos do termo e do associado.
- Corrigir a coluna `Valor / Repasse` para usar o valor disponível do contrato (`margem_disponivel` / disponível operacional) como valor do associado; o repasse do agente permanece como hoje.
- Em `Novos Contratos`, `Contratos para Renovação`, `Inadimplentes`, `Liquidação`, `Devoluções` e `Despesas`, substituir botões soltos por um controle dropdown de relatório com escolha de:
  - `Relatório do dia`
  - `Relatório do mês`
  - formato de saída
- `Tesouraria > Pagamentos` deixa de consumir `agente/pagamentos` e passa a ter endpoint próprio de tesouraria.
- `Inadimplentes` deve listar todas as parcelas não pagas do sistema, não só um mês fixo, e remover o calendário duplicado fora dos filtros avançados.
- Botões de detalhe do associado nas telas financeiras devem abrir modal expandido com os dados completos do associado, sem navegar para a rota de detalhe.
- `Liquidação` deve:
  - reduzir tempo de carregamento
  - remover cards do topo
  - corrigir filtros para não trazer associado sem parcela elegível na listagem padrão
  - adicionar ação de liquidação manual
- `Devoluções` deve:
  - permitir exclusão
  - corrigir KPI de duplicidades zerado
  - diferenciar corretamente a aba pós-liquidação da aba de registrar liquidação
- `Despesas` deve:
  - separar `despesas manuais` de `despesas avulsas`
  - tratar devoluções como `despesas avulsas`
  - revisar recorrências

### 3. Associados, Contratos, Importação e Dashboard de Ciclos
- Em associados e contratos, adicionar filtros por mês e por status/legenda do arquivo retorno.
- Os cards numéricos de importação devem abrir a listagem filtrada correspondente.
- `Dashboard de Ciclos` deve:
  - melhorar performance de carregamento
  - remover a seção `Monitoramento de ciclos (trimestral)`
  - remover cards `1/3`, `2/3`, `3/3`
  - remover o alerta de ausência de parcelas conciliadas
  - corrigir os cards internos mensais
- Na seção final de arquivo retorno, incluir card para `Valores 30/50`.
- Criar comando idempotente para varrer todos os arquivos retorno e corrigir os associados de 30 e 50 reais:
  - criar associado ausente
  - vincular ao `Agente Padrão ABASE`
  - gerar ou completar ciclos e parcelas desde outubro
  - tornar o associado visível na busca e na rota de associados
  - destravar criação de novas parcelas quando faltarem
- Após o comando, reprocessar/atualizar os arquivos retorno impactados para refletir o estado corrigido.

### 4. Coordenador e Aptos a renovar
- Separar a sidebar do coordenador da visão do analista, com ordem e nomenclatura próprias da rotina de coordenação.
- Manter URLs atuais por compatibilidade; a mudança vale para labels, headings, tabs, breadcrumbs e textos derivados.
- Em todos os perfis que hoje enxergam a tela de `/agentes/refinanciados`, trocar o nome para `Aptos a renovar`.
- Adicionar botão `Cancelar renovação` nessa frente.
- `Cancelar renovação` deve usar a regra existente de `desativar refinanciamento`, com motivo obrigatório.
- Adicionar modal de detalhes nessa frente reaproveitando o padrão visual/comportamental da coordenação em `refinanciados`.

### APIs, tipos e contratos públicos
- Adicionar `pendencia` ao enum público de `Ciclo.Status`.
- Estender o payload do admin editor para retornar `warnings` de sobreposição não bloqueantes.
- Criar endpoint próprio de listagem/resumo/exportação para `GET /api/v1/tesouraria/pagamentos/`.
- Registrar pagamentos do admin editor com origem explícita `admin_editor` para aparecerem na visão de pagamentos da tesouraria.
- Reutilizar a ação existente de desativação de refinanciamento para o novo botão `Cancelar renovação`.
- Padronizar exportações das telas financeiras para aceitar escopo de período `dia|mes` e referência selecionada no dropdown.

## Testes e cenários
- Admin editor:
  - salvar ajuste de ciclo simples
  - salvar `save-all` com edição de contrato + ciclos + parcelas
  - caso-regressão `Justino`
  - ciclo em `pendencia`
  - sobreposição com aviso e save permitido
  - anexos do admin editor aparecendo em `Tesouraria > Pagamentos`
- Tesouraria:
  - `/tesouraria` sem contratos antigos já pagos
  - reconciliação de pagos que ficaram pendentes
  - `Contratos para Renovação` com anexo do agente e valor correto do associado
  - `Tesouraria > Pagamentos` carregando via endpoint próprio
  - `Inadimplentes` listando parcelas não pagas de meses variados
  - modal expandido de associado abrindo sem sair da página
  - `Liquidação` sem associados sem parcelas na listagem padrão e com liquidação manual
  - exclusão de devolução e KPI de duplicidades corrigido
  - `Despesas` separando manuais e avulsas, com recorrência validada
- Associados/Importação/Ciclos:
  - filtros por mês e legenda do retorno
  - click-through dos cards de importação
  - dashboard de ciclos sem seção trimestral e com cards mensais corretos
  - comando idempotente de 30/50 criando/completando associados, ciclos e parcelas
- Coordenador/Aptos:
  - sidebar exclusiva do coordenador
  - labels `Aptos a renovar` em vez de `Renovações`
  - cancelar renovação usando `desativar`
  - modal de detalhes disponível nessa tela

## Assunções travadas
- Renomeações afetam apenas labels e títulos; URLs atuais permanecem.
- `Cancelar renovação` significa `desativar refinanciamento`, não criar status novo.
- Sobreposição no admin editor gera aviso, não bloqueio.
- `Pendência` de ciclo é status salvo em banco, não só estado visual.
- Correção dos associados 30/50 será feita por comando idempotente baseado em todos os arquivos retorno.
- Relatórios dessas telas usarão dropdown com escolha de período e formato, não dois botões fixos independentes.
