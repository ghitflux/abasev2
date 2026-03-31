# Rotinas Por Perfil e Mapa Completo de Rotas

Atualizado em: 31/03/2026

## Objetivo

Este documento descreve, com base no comportamento atual do frontend, quais perfis existem no sistema, qual é a rotina operacional esperada de cada um, quais rotas e subrotas estão disponíveis, o que cada tela faz e quais caminhos são compartilhados, legados ou aliases.

## Fontes de verdade consideradas

- `apps/web/src/lib/navigation.ts`
- `apps/web/src/hooks/use-permissions.ts`
- `apps/web/src/components/auth/role-guard.tsx`
- `apps/web/src/components/shared/legacy-route-redirect.tsx`
- páginas em `apps/web/src/app/(dashboard)`

## Perfis internos mapeados no sistema

Os perfis atualmente tratados pelo frontend são:

- `ADMIN`
- `AGENTE`
- `ANALISTA`
- `COORDENADOR`
- `TESOUREIRO`

## Regras gerais de acesso

- A rota `/` redireciona para `/login` quando não existe sessão e para `/dashboard` quando já existe token salvo.
- A rota `/login` redireciona o usuário autenticado para a rota padrão do seu perfil.
- A rota padrão por perfil é:

| Perfil | Rota padrão após login |
| --- | --- |
| `ADMIN` | `/dashboard` |
| `AGENTE` | `/agentes/meus-contratos` |
| `ANALISTA` | `/analise` |
| `COORDENADOR` | `/coordenacao/refinanciamento` |
| `TESOUREIRO` | `/tesouraria` |

- `ADMIN` tem acesso amplo ao sistema, com uma exceção relevante: a função `canAccessPath` bloqueia explicitamente `/tesouraria/confirmacoes`.
- `AGENTE` e `ANALISTA` conseguem abrir o detalhe do associado em `/associados/[id]`, mesmo sem acesso à listagem completa de associados.
- `COORDENADOR` consegue acessar:
  - `/dashboard`
  - `/associados`
  - `/associados/[id]`
  - `/configuracoes/usuarios`
  - `/configuracoes/comissoes`
  - `/importacao`
  - `/tesouraria/baixa-manual`
  - `/tesouraria/liquidacoes`
  - `/tesouraria/devolucoes`
  - páginas de coordenação
- `TESOUREIRO` consegue acessar:
  - tesouraria principal
  - `/agentes/pagamentos`
  - `/associados/[id]`
  - `/renovacao-ciclos`
- Existem caminhos legados compartilhados:
  - `/pagamentos`
  - `/renovacoes`
- Existem aliases internos mantidos para compatibilidade:
  - `/tesouraria/inadimplentes` redireciona para `/tesouraria/baixa-manual`
  - `/tesouraria/liquidacao` redireciona para `/tesouraria/liquidacoes`
  - `/tesouraria/devolucao` redireciona para `/tesouraria/devolucoes`

## Resumo executivo por perfil

| Perfil | Missão principal | Pode fazer em alto nível | Restrições mais importantes |
| --- | --- | --- | --- |
| `ADMIN` | Operar e auditar toda a plataforma | Acessar rotas de agente, análise, coordenação, tesouraria, dashboard executivo, relatórios, configurações e cadastro administrativo | Não acessa `/tesouraria/confirmacoes` pela regra atual do frontend |
| `AGENTE` | Captar, cadastrar, corrigir pendências e acompanhar contratos próprios | Cadastrar associado, acompanhar contratos, tratar pendências, acompanhar pagamentos e solicitar renovações dos próprios contratos | Não acessa dashboard executivo, coordenação, importação, relatórios, configurações, despesas e listagem geral de associados |
| `ANALISTA` | Validar documentação e encaminhar esteira | Trabalhar no dashboard analítico, revisar documentos, assumir itens, aprovar e enviar aptos para coordenação | Não acessa tesouraria operacional, importação, relatórios, configurações e listagem geral de associados |
| `COORDENADOR` | Validar renovações, supervisionar operação e atuar em filas financeiras específicas | Acessar dashboard executivo, lista de associados, filas de coordenação, importação, configurações e filas de inadimplência, liquidação e devolução | Não acessa tesouraria de novos contratos, renovações da tesouraria, despesas, relatórios administrativos e dashboard de ciclos |
| `TESOUREIRO` | Executar fluxo financeiro e registrar eventos operacionais | Efetivar novos contratos, operar pagamentos, renovações, inadimplentes, liquidações, devoluções, despesas e dashboard de ciclos | Não acessa dashboard executivo, importação, relatórios, configurações, análise e coordenação |

## Rotinas recomendadas por perfil

### 1. `ADMIN`

Rotina típica:

1. Entrar por `/dashboard` para leitura executiva da operação.
2. Acompanhar tesouraria, resumo mensal da associação, KPIs gerais e ranking de agentes.
3. Abrir `/associados` para supervisão da base, entrada no detalhe e auditoria operacional.
4. Usar `/associados/[id]` para análise completa do histórico e, quando necessário, ativar o modo administrativo.
5. Criar associados por `/associados/novo` e editar de forma administrativa por `/associados-editar/[id]`.
6. Acessar módulos de análise, coordenação e tesouraria quando precisar intervir no fluxo.
7. Operar `/importacao`, `/relatorios`, `/configuracoes/usuarios` e `/configuracoes/comissoes`.

Pode fazer com exclusividade ou maior poder:

- Criar usuário interno.
- Alterar perfis e senha em configurações de usuários.
- Criar associado pelo caminho administrativo.
- Entrar em modo de edição admin no detalhe do associado.
- Excluir associado.
- Acessar relatórios administrativos.

### 2. `AGENTE`

Rotina típica:

1. Entrar por `/agentes/meus-contratos`.
2. Acompanhar contratos próprios, evolução de ciclo, situação financeira e prontidão para renovação.
3. Usar `/agentes/cadastrar-associado` para iniciar novos cadastros.
4. Tratar correções em `/agentes/esteira-pendencias` quando o analista devolver cadastro.
5. Conferir repasses e comprovantes em `/agentes/pagamentos`.
6. Solicitar e acompanhar renovações em `/agentes/refinanciados`.
7. Abrir `/associados/[id]` quando precisar ver o detalhe de um associado específico.

Pode fazer:

- Criar associado no fluxo comercial.
- Corrigir dados e anexos devolvidos pela análise.
- Acompanhar contratos, parcelas, ciclos, histórico e pagamentos próprios.
- Solicitar renovação de contratos aptos.

Não faz:

- Gestão de usuários.
- Importação de retorno.
- Relatórios administrativos.
- Operação de tesouraria.
- Gestão de despesas.

### 3. `ANALISTA`

Rotina típica:

1. Entrar por `/analise`.
2. Trabalhar a fila consolidada, pendências, itens corrigidos, itens aguardando tesouraria e coordenação.
3. Abrir modal de documentos para revisar anexos e resumo do cadastro.
4. Assumir itens e encaminhar fluxos.
5. Usar `/analise/aptos` para revisar solicitações de renovação e encaminhá-las para coordenação.
6. Abrir `/associados/[id]` para consulta completa quando necessário.

Pode fazer:

- Revisar documentos.
- Trabalhar fila da esteira.
- Assumir análise.
- Aprovar ou devolver fluxos.
- Encaminhar contratos aptos para coordenação.

Não faz:

- Efetivação financeira.
- Gestão de despesas.
- Configurações.
- Importação.
- Relatórios administrativos.

### 4. `COORDENADOR`

Rotina típica:

1. Usar `/dashboard` para leitura executiva e acompanhamento macro.
2. Operar `/coordenacao/refinanciamento` para validação das renovações vindas da análise.
3. Operar `/coordenacao/refinanciados` para acompanhar renovados, em processo e itens enviados à liquidação.
4. Consultar `/associados` e `/associados/[id]` para leitura operacional.
5. Utilizar `/tesouraria/baixa-manual`, `/tesouraria/liquidacoes` e `/tesouraria/devolucoes` quando o fluxo exigir participação da coordenação.
6. Operar `/importacao` e as configurações de usuários e comissões.

Pode fazer:

- Validar renovações.
- Enviar contratos para tesouraria.
- Cancelar renovação e encaminhar para liquidação.
- Acompanhar base de associados.
- Gerir usuários e comissões.
- Operar importação.

Não faz:

- Relatórios administrativos.
- Despesas da associação.
- Fluxo de novos contratos da tesouraria.
- Renovações financeiras executadas pela tesouraria.

### 5. `TESOUREIRO`

Rotina típica:

1. Entrar por `/tesouraria`.
2. Operar novos contratos e efetivação financeira.
3. Consultar `/agentes/pagamentos` para pagamentos operacionais e evidências.
4. Trabalhar `/tesouraria/refinanciamentos` para renovações já validadas.
5. Registrar baixa manual em `/tesouraria/baixa-manual`.
6. Registrar e reverter liquidações em `/tesouraria/liquidacoes`.
7. Registrar devoluções e tratar duplicidades em `/tesouraria/devolucoes`.
8. Controlar lançamentos e resultado em `/tesouraria/despesas`.
9. Acompanhar competência e conciliação em `/renovacao-ciclos`.

Pode fazer:

- Efetivar novos contratos.
- Registrar comprovantes financeiros.
- Operar pagamentos, renovações e baixas.
- Registrar liquidações, devoluções e despesas.
- Ler detalhe do associado.

Não faz:

- Gestão de usuários.
- Importação.
- Relatórios administrativos.
- Dashboard executivo.
- Esteira de análise.

## Catálogo completo de rotas e subrotas

### A. Rotas públicas e de entrada

#### `/`

- Tipo: entrada raiz do sistema.
- Acesso: público.
- Função: redireciona para `/login` quando não há sessão e para `/dashboard` quando já existe token.

#### `/login`

- Tipo: autenticação.
- Acesso: público.
- Função: exibe o formulário de login.
- Comportamento após autenticação: redireciona para a rota padrão do perfil.

### B. Rotas legadas compartilhadas

#### `/pagamentos`

- Tipo: rota legada.
- Acesso: compartilhado por regra de redirecionamento.
- Função: não tem tela própria; redireciona conforme o perfil:
  - `AGENTE`, `TESOUREIRO` e `ADMIN` vão para `/agentes/pagamentos`
  - demais perfis voltam para a rota padrão

#### `/renovacoes`

- Tipo: rota legada.
- Acesso: compartilhado por regra de redirecionamento.
- Função: não tem tela própria; redireciona conforme o perfil:
  - `TESOUREIRO` e `ADMIN` vão para `/renovacao-ciclos`
  - `COORDENADOR` vai para `/coordenacao/refinanciamento`
  - `AGENTE` vai para `/agentes/refinanciados`
  - demais perfis voltam para a rota padrão

### C. Visão Geral

#### `/dashboard`

- Menu: `Visão Geral > Dashboard`
- Perfis: `ADMIN`, `COORDENADOR`
- Função: dashboard executivo consolidado.
- Blocos principais:
  - Tesouraria
  - Resumo mensal da associação
  - KPIs gerais
  - Novos associados
  - Agentes
- Ações principais:
  - aplicar filtros por seção
  - abrir detalhamento por métrica
  - exportar dados em blocos específicos

### D. Operação > Cadastros

#### `/agentes/meus-contratos`

- Menu: `Operação > Cadastros > Meus Contratos`
- Perfis: `AGENTE`, `ADMIN`
- Função:
  - para `AGENTE`: acompanhar contratos próprios, quitações do ciclo atual e prontidão para renovação
  - para `ADMIN`: visão consolidada de todos os contratos
- Filtros e subfluxos:
  - busca por contrato, associado, CPF, matrícula e agente
  - filtros avançados por período, competência, status do contrato, etapa do fluxo e faixa de valores
  - expansão de linhas para dados complementares do contrato
- Ações principais:
  - abrir detalhe do associado
  - acompanhar situação financeira do contrato

#### `/agentes/cadastrar-associado`

- Menu: `Operação > Cadastros > Cadastrar Associado`
- Perfis: `AGENTE`
- Função: iniciar cadastro de novo associado no fluxo comercial.
- Observações:
  - usa o formulário principal de associado em modo de criação
  - retorno de cancelamento vai para `/agentes/meus-contratos`
  - sucesso leva ao detalhe `/associados/[id]`

#### `/associados`

- Menu: `Operação > Cadastros > Associados`
- Perfis: `ADMIN`, `COORDENADOR`
- Função: visão operacional da base de associados.
- KPIs principais:
  - total de associados
  - ativos
  - em análise
  - inativos
  - liquidados
- Subrotas e comportamentos internos:
  - tabela com filtros avançados por status, agente, órgão público, número de ciclos e perfil do ciclo
  - expansão da linha para painel de ciclos
  - diálogo de detalhamento por KPI
- Ações principais:
  - abrir `/associados/[id]`
  - analisar ciclos e parcelas

#### `/agentes/esteira-pendencias`

- Menu: `Operação > Cadastros > Esteira de Pendências`
- Perfis: `AGENTE`, `ADMIN`
- Função: tratar itens devolvidos ao agente para correção de cadastro.
- KPIs principais:
  - pendências abertas
  - retornadas ao agente
  - tratamento interno
  - associados impactados
- Subfluxos:
  - painel de pendências
  - diálogo de correção de cadastro
- Ações principais:
  - ajustar dados
  - substituir anexos
  - reenviar item para análise

#### `/agentes/refinanciados`

- Menu: `Operação > Cadastros > Refinanciados`
- Perfis: `AGENTE`, `ADMIN`
- Função: gerir solicitações de renovação dos próprios contratos.
- Abas:
  - `Solicitações e histórico`
  - `Aptos a renovar`
- KPIs típicos:
  - solicitações do agente
  - em análise
  - aguardando coordenação
  - com termo do agente
- Ações principais:
  - enviar termo
  - acompanhar andamento
  - identificar contratos aptos para renovação

#### `/agentes/pagamentos`

- Menu:
  - `Operação > Cadastros > Pagamentos` para `AGENTE`
  - `Financeiro > Tesouraria > Pagamentos` para `TESOUREIRO` e `ADMIN`
- Perfis: `AGENTE`, `TESOUREIRO`, `ADMIN`
- Função: visualizar repasses e pagamentos operacionais ligados a contratos.
- KPIs principais:
  - contratos com repasse
  - efetivados
  - com anexos
  - parcelas pagas
- Subfluxos:
  - seção de pagamento inicial da efetivação
  - seções por ciclo com parcelas e comprovantes
- Ações principais:
  - conferir evidências
  - consultar histórico de pagamento operacional

### E. Operação > Análise

#### `/analise`

- Menu: `Operação > Análise > Dashboard Análise`
- Perfis: `ANALISTA`, `ADMIN`
- Função: painel consolidado das filas da esteira de análise.
- Seções internas do fluxo:
  - ver todos
  - pendências
  - corrigidos
  - enviado para tesouraria
  - enviado para coordenação
  - efetivados
  - cancelados
- Filtros:
  - busca por nome, CPF, matrícula ou contrato
  - agente
  - analista responsável
  - etapa
  - status
  - intervalo de datas
- Ações principais:
  - assumir item
  - abrir modal de documentos e formulário
  - ver detalhes completos
  - acompanhar pendências

#### `/analise/aptos`

- Menu: `Operação > Análise > Aptos a Renovar`
- Perfis: `ANALISTA`, `ADMIN`
- Função: fila de contratos para renovação enviada pelo agente.
- KPIs principais:
  - total
  - em análise
  - assumidos
  - aprovados
- Filtros:
  - competência inicial e final
  - agente
  - status
  - origem
  - responsável
- Ações principais:
  - assumir item
  - revisar solicitação
  - aprovar e enviar para coordenação

### F. Operação > Coordenação

#### `/coordenacao/refinanciamento`

- Menu: `Operação > Análise > Refinanciamento`
- Perfis: `COORDENADOR`, `ADMIN`
- Função: fila de coordenação com renovações enviadas pelo analista.
- Filtros:
  - busca textual
  - ano
  - agente
  - competência inicial e final
  - status
  - origem
  - faixa de elegibilidade
- Ações principais:
  - validar renovação
  - aprovar
  - enviar em lote para tesouraria
  - encaminhar contrato para liquidação

#### `/coordenacao/refinanciados`

- Menu: `Operação > Análise > Refinanciados`
- Perfis: `COORDENADOR`, `ADMIN`
- Função: acompanhar renovações após a coordenação.
- KPIs principais:
  - total
  - renovados
  - em processo
  - em liquidação
- Seções:
  - contratos renovados
  - contratos em processo de renovação
  - contratos em liquidação
- Ações principais:
  - cancelar renovação
  - imprimir/PDF
  - acompanhar desvio para liquidação

### G. Financeiro > Tesouraria

#### `/tesouraria`

- Menu: `Financeiro > Tesouraria > Novos Contratos`
- Perfis: `TESOUREIRO`, `ADMIN`
- Função: operar o fluxo padrão de novos contratos na competência ativa.
- Seções principais:
  - pendentes
  - pagos
  - cancelados
- Filtros:
  - competência
  - período
  - agente
  - status do contrato
  - situação operacional
- Ações principais:
  - efetivar contrato
  - abrir dados bancários para PIX
  - congelar contrato com motivo
  - abrir detalhe completo do associado/contrato/ciclos

#### `/tesouraria/refinanciamentos`

- Menu: `Financeiro > Tesouraria > Renovações`
- Perfis: `TESOUREIRO`, `ADMIN`
- Função: executar financeiramente renovações validadas pela coordenação.
- Abas:
  - `Renovações Pendentes`
  - `Renovações Efetuadas`
  - `Renovações Canceladas`
- KPIs principais:
  - total da aba filtrada
  - efetivadas
  - canceladas
  - repasse total
- Ações principais:
  - efetivar renovação
  - consultar histórico financeiro por status

#### `/tesouraria/baixa-manual`

- Menu: `Financeiro > Tesouraria > Inadimplentes`
- Perfis: `TESOUREIRO`, `COORDENADOR`, `ADMIN`
- Função: tratar parcelas anteriores pendentes ou não descontadas.
- KPIs principais:
  - total pendentes
  - em aberto
  - não descontadas
  - valor total pendente
- Filtros:
  - busca
  - status
  - competência
- Ações principais:
  - registrar baixa manual
  - anexar comprovante
  - informar valor pago
  - registrar observação

#### `/tesouraria/liquidacoes`

- Menu: `Financeiro > Tesouraria > Liquidação`
- Perfis: `TESOUREIRO`, `COORDENADOR`, `ADMIN`
- Função: registrar liquidações e consultar histórico.
- Visões principais:
  - fila elegível
  - histórico de liquidados
- KPIs típicos:
  - total na fila
  - liquidáveis agora
  - sem parcelas elegíveis
  - valor potencial
  - contratos liquidados
  - parcelas liquidadas
  - valor liquidado
  - liquidações revertidas
- Ações principais:
  - registrar liquidação
  - anexar comprovantes
  - informar origem e observação
  - reverter liquidação

#### `/tesouraria/devolucoes`

- Menu: `Financeiro > Tesouraria > Devoluções`
- Perfis: `TESOUREIRO`, `COORDENADOR`, `ADMIN`
- Função: registrar devoluções por pagamento ou desconto indevido e tratar duplicidades financeiras.
- Abas:
  - `Registrar`
  - `Pós-liquidação`
  - `Duplicidades`
  - `Histórico`
- Filtros:
  - competência
  - tipo
  - estado do fluxo
  - status
- Ações principais:
  - lançar devolução
  - lançar devolução manual
  - editar devolução ativa
  - tratar duplicidades de retorno
  - consultar histórico
- Regras de permissão relevantes:
  - edição liberada para coordenação, tesouraria e admin
  - exclusão e reversão permanecem restritas ao admin

#### `/tesouraria/despesas`

- Menu: `Financeiro > Tesouraria > Despesas`
- Perfis: `TESOUREIRO`, `ADMIN`
- Função: controlar lançamentos manuais e resultado mensal da associação.
- Abas:
  - `Lançamentos`
  - `Resultado mensal`
- Subabas do detalhe mensal:
  - `Geral`
  - `Receitas`
  - `Despesas`
- Filtros em lançamentos:
  - status financeiro
  - status do anexo
  - tipo
  - natureza
- Filtros no resultado:
  - agente
  - janela fixa dos últimos 12 meses incluindo o mês atual
- Ações principais:
  - novo lançamento manual
  - lançamento como despesa operacional
  - lançamento como complemento de receita
  - abrir detalhe do mês
  - consultar composição, receitas, despesas e pagamentos operacionais

#### `/tesouraria/confirmacoes`

- Tipo: página implementada, porém atualmente bloqueada pela regra de acesso do frontend.
- Acesso prático atual: indisponível.
- Função da tela:
  - colar link de chamada
  - confirmar ligação
  - confirmar averbação
- Observação:
  - apesar de existir a página, `canAccessPath` retorna bloqueio para qualquer navegação nesse prefixo

### H. Financeiro > Outras rotas

#### `/importacao`

- Menu: `Financeiro > Importação`
- Perfis: `ADMIN`, `COORDENADOR`
- Função: importar relatório de retorno em `.txt` no formato ETIPI/iNETConsig.
- Seções e abas principais:
  - resumo da última importação
  - resumo financeiro
  - `Descontados`
  - `Não descontados`
  - `Pendências`
  - `Encerramentos`
  - `Novos ciclos`
  - histórico de importações
- Ações principais:
  - subir arquivo
  - acompanhar processamento
  - reprocessar arquivo
  - consultar itens reconciliados e pendentes

#### `/renovacao-ciclos`

- Menu: `Financeiro > Dashboard de Ciclos`
- Perfis: `ADMIN`, `TESOUREIRO`
- Função: gestão detalhada da competência, reconciliação por arquivo retorno e monitoramento de ciclos.
- Blocos funcionais:
  - visão da competência atual
  - monitoramento por estágio
  - leitura trimestral e semestral
  - detalhamento por arquivo retorno
- Filtros:
  - competência
  - datas
  - agente
  - status
  - faixas e segmentos
- Ações principais:
  - abrir diálogos de detalhe por métrica
  - consultar arquivos retorno
  - acompanhar inadimplência e encerramentos de ciclo

#### `/relatorios`

- Menu: `Financeiro > Relatórios`
- Perfis: `ADMIN`
- Função: repositório administrativo de indicadores e exportações.
- Blocos principais:
  - resumo executivo
  - opções de exportação
  - histórico de relatórios gerados
- Ações principais:
  - gerar exportações
  - consultar histórico de geração
- Observação:
  - a própria página informa que o módulo é exclusivo do perfil `ADMIN`

### I. Administração > Configurações

#### `/configuracoes/usuarios`

- Menu: `Administração > Configurações > Usuários`
- Perfis: `ADMIN`, `COORDENADOR`
- Função: gestão centralizada de acessos internos.
- Ações principais:
  - criar novo usuário
  - ativar ou desativar acesso
  - ajustar perfis
  - redefinir senha
- KPIs típicos:
  - usuários internos
  - acessos ativos
  - administradores
  - troca de senha

#### `/configuracoes/comissoes`

- Menu: `Administração > Configurações > Comissões`
- Perfis: `ADMIN`, `COORDENADOR`
- Função: gerenciar percentual global e overrides por agente.
- Seções principais:
  - regra global
  - override por agente
  - agentes e comissão efetiva
- Ações principais:
  - alterar percentual global
  - registrar motivo
  - aplicar override individual

### J. Rotas de associado e administração de cadastro

#### `/associados/[id]`

- Tipo: detalhe do associado.
- Perfis: `ADMIN`, `AGENTE`, `ANALISTA`, `COORDENADOR`, `TESOUREIRO`
- Função: visão completa do associado, seus contratos, documentos, ciclos e dados cadastrais.
- Seções típicas:
  - dados pessoais
  - documentos
  - contratos e ciclos
  - endereço
  - histórico operacional
- Ações principais por perfil:
  - todos os perfis liberados podem consultar
  - `ADMIN` pode ativar `Modo edição admin`
  - `ADMIN` pode abrir `Editar cadastro`
  - `ADMIN` pode excluir associado
- Observações:
  - o botão de voltar muda conforme o perfil de origem
  - a tela protege saída quando há alterações administrativas pendentes

#### `/associados/novo`

- Tipo: criação administrativa de associado.
- Perfis: `ADMIN`
- Função: abrir o formulário principal de associado em modo de criação.

#### `/associados-editar/[id]`

- Tipo: edição administrativa dedicada.
- Perfis: `ADMIN`
- Função: abrir o editor administrativo do associado identificado.
- Observações:
  - aceita `?admin=1` para iniciar em modo administrativo

### K. Aliases mantidos para compatibilidade

#### `/tesouraria/inadimplentes`

- Tipo: alias.
- Destino: `/tesouraria/baixa-manual`
- Perfis que acabam atendidos: os mesmos da rota destino

#### `/tesouraria/liquidacao`

- Tipo: alias.
- Destino: `/tesouraria/liquidacoes`
- Perfis que acabam atendidos: os mesmos da rota destino

#### `/tesouraria/devolucao`

- Tipo: alias.
- Destino: `/tesouraria/devolucoes`
- Perfis que acabam atendidos: os mesmos da rota destino

## Mapa rápido de rotas por perfil

### `ADMIN`

- `/dashboard`
- `/agentes/meus-contratos`
- `/agentes/esteira-pendencias`
- `/agentes/refinanciados`
- `/agentes/pagamentos`
- `/analise`
- `/analise/aptos`
- `/coordenacao/refinanciamento`
- `/coordenacao/refinanciados`
- `/tesouraria`
- `/tesouraria/refinanciamentos`
- `/tesouraria/baixa-manual`
- `/tesouraria/liquidacoes`
- `/tesouraria/devolucoes`
- `/tesouraria/despesas`
- `/importacao`
- `/renovacao-ciclos`
- `/relatorios`
- `/configuracoes/usuarios`
- `/configuracoes/comissoes`
- `/associados`
- `/associados/[id]`
- `/associados/novo`
- `/associados-editar/[id]`

### `AGENTE`

- `/agentes/meus-contratos`
- `/agentes/cadastrar-associado`
- `/agentes/esteira-pendencias`
- `/agentes/refinanciados`
- `/agentes/pagamentos`
- `/associados/[id]`

### `ANALISTA`

- `/analise`
- `/analise/aptos`
- `/associados/[id]`

### `COORDENADOR`

- `/dashboard`
- `/coordenacao/refinanciamento`
- `/coordenacao/refinanciados`
- `/tesouraria/baixa-manual`
- `/tesouraria/liquidacoes`
- `/tesouraria/devolucoes`
- `/importacao`
- `/configuracoes/usuarios`
- `/configuracoes/comissoes`
- `/associados`
- `/associados/[id]`

### `TESOUREIRO`

- `/tesouraria`
- `/agentes/pagamentos`
- `/tesouraria/refinanciamentos`
- `/tesouraria/baixa-manual`
- `/tesouraria/liquidacoes`
- `/tesouraria/devolucoes`
- `/tesouraria/despesas`
- `/renovacao-ciclos`
- `/associados/[id]`

## Pontos de atenção e lacunas atuais

- `/tesouraria/confirmacoes` existe como página, mas hoje está bloqueada na camada de acesso do frontend.
- `/pagamentos` e `/renovacoes` não devem ser documentadas como telas finais; são apenas rotas legadas de redirecionamento.
- Os aliases `/tesouraria/inadimplentes`, `/tesouraria/liquidacao` e `/tesouraria/devolucao` existem para compatibilidade, mas o fluxo principal deve usar:
  - `/tesouraria/baixa-manual`
  - `/tesouraria/liquidacoes`
  - `/tesouraria/devolucoes`

## Recomendações de manutenção

- Sempre que uma nova rota for criada, atualizar este documento junto com `navigation.ts`.
- Sempre que um perfil ganhar acesso especial via `canAccessPath`, registrar aqui a exceção.
- Sempre que uma tela trocar de função, revisar a seção "Rotinas por perfil" e o bloco "Catálogo completo de rotas e subrotas".
