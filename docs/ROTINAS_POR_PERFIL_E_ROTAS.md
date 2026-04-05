# Rotinas, Perfis, Fluxos e Mapa de Rotas da Aplicação

Atualizado em: 04/04/2026

## Objetivo

Este documento consolida o entendimento funcional da aplicação ABASE no estado atual do código. Ele serve para operação, suporte, onboarding técnico e validação de deploy.

O foco aqui não é só listar telas. O objetivo é explicar:

- qual é a missão do sistema
- quais módulos compõem a operação
- quais entidades de negócio se relacionam
- como cada perfil trabalha no fluxo
- quais rotas existem hoje no frontend
- quais pontos exigem atenção operacional

## O que a aplicação faz

A ABASE é uma plataforma operacional e financeira para gestão do ciclo do associado, desde o cadastro inicial até a efetivação financeira, acompanhamento de parcelas, importação de arquivo retorno, renovação, liquidação, devolução e auditoria administrativa.

O sistema é dividido em dois grandes eixos:

- eixo operacional: cadastro, análise, coordenação, esteira e acompanhamento do associado
- eixo financeiro: tesouraria, parcelas, importação de retorno, ciclos, renovações, liquidações, devoluções, despesas e relatórios

Na prática, a aplicação responde a 7 perguntas principais:

1. Quem é o associado e em que estado operacional ele está?
2. Qual é o contrato ativo ou histórico desse associado?
3. Quais ciclos e parcelas existem e o que foi pago, previsto, liquidado ou devolvido?
4. Quais evidências documentais e comprovantes estão anexados?
5. O que depende do agente, da análise, da coordenação ou da tesouraria?
6. O que veio do arquivo retorno e o que foi lançado manualmente?
7. O associado está ativo, inadimplente, apto a renovar, liquidado ou fora do fluxo?

## Visão de arquitetura funcional

Os módulos principais da aplicação são estes:

| Módulo | Papel |
| --- | --- |
| `Cadastros` | base de associados, contratos e acompanhamento operacional |
| `Esteira / Análise` | valida documentos, devolve pendências e aprova encaminhamentos |
| `Coordenação` | valida refinanciamentos e encaminha para tesouraria |
| `Tesouraria` | efetiva contratos, registra baixas, liquidações, devoluções e despesas |
| `Importação` | lê arquivo retorno ETIPI/iNETConsig, simula, confirma e processa |
| `Ciclos` | projeta, reconstrói e monitora materialização de ciclos e parcelas |
| `Configurações` | usuários internos, comissões e redistribuição de carteira |
| `Autenticação` | login web, sessão, logout e recuperação manual de senha do agente |
| `Mobile` | cadastro e autoatendimento do associado via app |

## Entidades centrais do domínio

### `Associado`

É o eixo principal do sistema. Todo o resto se organiza em torno dele.

Campos e usos mais importantes:

- identidade civil e contato
- CPF/CNPJ
- matrícula do servidor
- órgão público
- status operacional do associado
- agente responsável
- vínculo com usuário do app mobile, quando existir

### `Contrato`

Representa a concessão financeira principal do associado.

Informações relevantes:

- código do contrato
- agente responsável
- valor bruto, líquido e disponível
- mensalidade associativa
- taxa de antecipação
- comissão do agente
- status do contrato

### `Ciclo`

É o agrupador cronológico de parcelas de um contrato. A aplicação depende fortemente da materialização correta dos ciclos para:

- aptidão de renovação
- inadimplência
- liquidação
- dashboard de ciclos
- detalhe do associado

### `Parcela`

É a competência mensal materializada do contrato.

Estados operacionais típicos:

- `em_previsao`
- `descontado`
- `nao_descontado`
- `liquidada`

### `PagamentoMensalidade`

É a trilha financeira por competência. Nem todo pagamento manual necessariamente compõe ciclo. Hoje isso é uma distinção importante.

Casos relevantes:

- retorno importado que conta para ciclo
- pagamento manual que conta para ciclo
- pagamento manual quitado fora do ciclo
- pagamento manual cancelado para não contaminar projeção

### `BaixaManual`

É a evidência manual de regularização aplicada sobre parcela, usada historicamente para inadimplência e saneamentos financeiros.

### `ArquivoRetorno` e `ArquivoRetornoItem`

Representam o arquivo retorno importado e cada linha reconciliada.

Hoje o fluxo não processa mais direto no upload. Primeiro existe uma prévia com `dry-run`, depois confirmação explícita.

### `EsteiraItem`

É o item operacional da fila de análise.

Ele liga o cadastro à rotina dos analistas, coordenação e eventual retorno ao agente.

### `Solicitação de Refinanciamento`

Organiza a renovação do contrato, desde a intenção do agente até a decisão da coordenação e a efetivação financeira pela tesouraria.

## Perfis internos e missão operacional

Os perfis tratados pelo frontend hoje são:

- `ADMIN`
- `AGENTE`
- `ANALISTA`
- `COORDENADOR`
- `TESOUREIRO`

Rotas padrão após login:

| Perfil | Rota padrão |
| --- | --- |
| `ADMIN` | `/dashboard` |
| `AGENTE` | `/agentes/meus-contratos` |
| `ANALISTA` | `/analise` |
| `COORDENADOR` | `/coordenacao/refinanciamento` |
| `TESOUREIRO` | `/tesouraria` |

## Regras gerais de autenticação e acesso

- `/` redireciona para `/login` sem sessão e para a rota padrão quando já existe autenticação
- `/login` redireciona o usuário autenticado para a rota padrão do seu perfil
- existe recuperação manual de senha do agente em `/login/recuperar-senha`
- a sessão web foi ampliada para 48h de access token, com refresh separado
- `ADMIN` tem acesso amplo, mas a regra atual do frontend bloqueia `/tesouraria/confirmacoes`
- `AGENTE` e `ANALISTA` conseguem abrir `/associados/[id]` mesmo sem acesso à listagem completa de associados
- `COORDENADOR` possui exceções explícitas para `associados`, `configurações`, `importação` e algumas filas da tesouraria
- `TESOUREIRO` acessa o detalhe do associado e o fluxo financeiro, mas não acessa importação, relatórios administrativos ou configuração

## Fluxo ponta a ponta da aplicação

### 1. Cadastro do associado

A entrada pode acontecer por três caminhos:

- agente comercial
- administração
- fluxo mobile

Fluxo típico:

1. o cadastro é criado
2. documentos e dados ficam disponíveis para revisão
3. um item é criado na esteira
4. a análise valida, devolve ou encaminha
5. aprovado, o fluxo segue para efetivação financeira

### 2. Análise documental e esteira

O módulo de análise não é financeiro. Ele decide se o cadastro está consistente o suficiente para seguir.

O analista faz:

- assumir item
- revisar anexos
- devolver correções
- aprovar e encaminhar

Esse módulo impacta diretamente:

- visibilidade do cadastro
- andamento do contrato
- transição para coordenação ou tesouraria

### 3. Efetivação de contrato na tesouraria

Depois da aprovação operacional, a tesouraria efetiva:

- valor pago
- comprovantes da efetivação
- evidências do associado e do agente
- criação e materialização do contrato e do ciclo

É a partir daqui que o detalhe do associado ganha peso financeiro real.

### 4. Importação de arquivo retorno

Hoje o fluxo correto é:

1. upload do `.txt`
2. `dry-run` síncrono
3. abertura do modal de prévia
4. confirmação explícita ou cancelamento
5. processamento assíncrono

Isso existe para impedir escrita irreversível a partir de arquivo errado, competência errada ou duplicidade.

Impactos da importação:

- desconto de parcelas
- não desconto
- encerramentos
- novos ciclos
- aptidão de renovação
- inadimplência

### 5. Renovação / refinanciamento

O fluxo de renovação cruza quatro perfis:

1. agente identifica contrato apto
2. análise revisa solicitação
3. coordenação aprova ou desvia
4. tesouraria efetiva a renovação

Esse fluxo usa:

- aptidão baseada em ciclo
- documentos e termos
- envio para liquidação quando necessário

### 6. Inadimplência, baixa manual, liquidação e devolução

Esse é o fluxo de exceção financeira.

Ele resolve:

- competência não descontada
- pagamento manual fora do retorno
- liquidação de contrato
- devoluções por desconto indevido
- duplicidades financeiras

É também a área mais sensível para inconsistência de ciclo e projeção.

### 7. Administração e segurança operacional

As telas administrativas hoje cobrem:

- usuários internos
- comissões
- redistribuição de carteira ao desativar ou remover papel `AGENTE`
- recuperação manual de senha para agente

A redistribuição de carteira é bloqueante: um agente com associados vinculados não pode perder acesso sem transferência explícita da base.

## Regras operacionais importantes já incorporadas

### Importação com confirmação

O arquivo retorno não processa automaticamente após o upload. O estado `aguardando_confirmacao` agora é parte oficial da rotina.

### Redistribuição de carteira

Ao remover ou desativar um `AGENTE`, o sistema exige escolher um agente destino se houver associados sob responsabilidade dele.

Essa sincronização afeta:

- `Associado.agente_responsavel`
- `Contrato.agente`

### Recuperação manual de senha do agente

Existe fluxo público específico para agente, sem token externo, com validação de e-mail existente no sistema.

### Distinção entre pagamento manual em ciclo e fora do ciclo

Hoje essa distinção é estrutural para não quebrar projeção:

- `conciliacao_maristela_em_ciclo`
- `conciliacao_maristela_fora_ciclo`

Na prática:

- março/2026 manual pode compor ciclo
- novembro/2025 manual pode permanecer quitado fora do ciclo

### Importação cronológica de retorno legado

Há comando específico para reimportar arquivos staged em ordem cronológica, com uso combinado com saneamentos financeiros.

## Rotinas recomendadas por perfil

### `ADMIN`

Missão:

- supervisionar toda a operação
- intervir em qualquer módulo
- auditar inconsistências
- administrar usuários e regras de comissão

Rotina típica:

1. entrar por `/dashboard`
2. acompanhar KPIs executivos
3. supervisionar `Associados`, `Importação`, `Tesouraria` e `Relatórios`
4. abrir `/associados/[id]` para auditoria profunda
5. usar modo de edição admin quando a correção exigir intervenção
6. operar usuários internos, comissões e redistribuição de carteira

Pode fazer:

- criar usuário interno
- redefinir acessos e perfis
- redistribuir carteira ao desativar agente
- criar ou editar associado em modo administrativo
- excluir associado
- acessar relatórios administrativos

### `AGENTE`

Missão:

- captar e cadastrar
- corrigir devoluções
- acompanhar contratos próprios
- solicitar renovação

Rotina típica:

1. entrar por `/agentes/meus-contratos`
2. acompanhar contratos e ciclos
3. cadastrar por `/agentes/cadastrar-associado`
4. tratar devoluções em `/agentes/esteira-pendencias`
5. conferir repasses e comprovantes em `/agentes/pagamentos`
6. acompanhar renovações em `/agentes/refinanciados`

Não faz:

- importação
- gestão de usuários
- relatórios administrativos
- tesouraria operacional

### `ANALISTA`

Missão:

- validar documentação
- controlar a esteira
- decidir se o fluxo segue ou retorna

Rotina típica:

1. entrar por `/analise`
2. trabalhar a fila consolidada
3. revisar documentos e resumo do cadastro
4. assumir item
5. devolver correções ou aprovar
6. usar `/analise/aptos` para refinanciamentos

Não faz:

- efetivação financeira
- liquidação
- devolução
- importação
- configurações

### `COORDENADOR`

Missão:

- supervisionar refinanciamento
- operar validação intermediária
- atuar em filas financeiras específicas

Rotina típica:

1. entrar por `/coordenacao/refinanciamento`
2. validar solicitações vindas da análise
3. acompanhar contratos em `/coordenacao/refinanciados`
4. consultar associados e contratos
5. operar importação quando necessário
6. atuar em baixa manual, liquidação e devolução quando o fluxo exigir
7. gerir usuários e comissões dentro do escopo permitido

### `TESOUREIRO`

Missão:

- efetivar novos contratos
- operar baixas, liquidações, devoluções e despesas
- acompanhar ciclos e competências

Rotina típica:

1. entrar por `/tesouraria`
2. efetivar contratos pendentes
3. consultar `/tesouraria/pagamentos`
4. operar renovações em `/tesouraria/refinanciamentos`
5. atuar em inadimplentes por `/tesouraria/baixa-manual`
6. registrar liquidações e devoluções
7. acompanhar competência em `/renovacao-ciclos`

## Catálogo de rotas atual

### Rotas públicas e de autenticação

#### `/`

- entrada raiz
- redireciona para `/login` sem sessão
- redireciona para a rota padrão do perfil quando autenticado

#### `/login`

- formulário principal de autenticação
- entrada padrão do web
- contém link para recuperação manual de senha

#### `/login/recuperar-senha`

- fluxo público de recuperação manual de senha para agente
- não usa token externo
- depende de validação do e-mail cadastrado e nova senha

### Rotas legadas compartilhadas

#### `/pagamentos`

- rota legada de redirecionamento
- não é tela final
- encaminha conforme o perfil

#### `/renovacoes`

- rota legada de redirecionamento
- não é tela final
- encaminha para ciclos, coordenação ou renovações do agente conforme o perfil

### Visão geral

#### `/dashboard`

- perfis: `ADMIN`, `COORDENADOR`
- função: visão executiva consolidada
- blocos: KPIs gerais, tesouraria, resumo mensal e ranking operacional

### Operação > Cadastros

#### `/agentes/meus-contratos`

- perfis: `AGENTE`, `ADMIN`
- para agente: contratos próprios
- para admin: visão consolidada
- principais ações:
  - abrir detalhe do associado
  - expandir linha do contrato
  - consultar valor disponível, ciclo atual e situação do contrato

#### `/agentes/cadastrar-associado`

- perfis: `AGENTE`
- criação comercial de associado

#### `/associados`

- perfis: `ADMIN`, `COORDENADOR`
- listagem operacional da base
- possui KPIs, filtros e expansão de ciclos

#### `/associados/novo`

- perfis: `ADMIN`, `COORDENADOR`, `ANALISTA`
- formulário de criação na rotina administrativa

#### `/associados/[id]`

- perfis: `ADMIN`, `AGENTE`, `ANALISTA`, `COORDENADOR`, `TESOUREIRO`
- visão completa do associado
- concentra:
  - dados pessoais
  - documentos
  - contratos
  - ciclos e parcelas
  - evidências financeiras
  - histórico operacional

#### `/associados-editar/[id]`

- perfis: `ADMIN`
- edição administrativa dedicada

#### `/agentes/esteira-pendencias`

- perfis: `AGENTE`, `ADMIN`
- correção de itens devolvidos

#### `/agentes/refinanciados`

- perfis: `AGENTE`, `ADMIN`
- gestão de solicitações de renovação e contratos aptos

#### `/agentes/pagamentos`

- perfis: `AGENTE`, `TESOUREIRO`, `ADMIN`
- histórico de repasses e comprovantes operacionais

### Operação > Análise

#### `/analise`

- perfis: `ANALISTA`, `COORDENADOR`, `ADMIN`
- dashboard da esteira de análise

#### `/analise/aptos`

- perfis: `ANALISTA`, `ADMIN`
- fila de contratos para renovação antes da coordenação

#### `/coordenacao/refinanciamento`

- perfis: `COORDENADOR`, `ADMIN`
- fila de aprovação da coordenação

#### `/coordenacao/refinanciados`

- perfis: `COORDENADOR`, `ADMIN`
- acompanhamento posterior das renovações

### Financeiro > Tesouraria

#### `/tesouraria`

- perfis: `TESOUREIRO`, `ADMIN`
- novos contratos

#### `/tesouraria/pagamentos`

- perfis: `TESOUREIRO`, `ADMIN`
- pagamentos e evidências da efetivação

#### `/tesouraria/refinanciamentos`

- perfis: `TESOUREIRO`, `ADMIN`
- efetivação financeira das renovações

#### `/tesouraria/baixa-manual`

- perfis: `TESOUREIRO`, `COORDENADOR`, `ADMIN`
- tratamento de inadimplência e regularização manual

#### `/tesouraria/liquidacoes`

- perfis: `TESOUREIRO`, `COORDENADOR`, `ADMIN`
- liquidação e histórico de liquidados

#### `/tesouraria/devolucoes`

- perfis: `TESOUREIRO`, `COORDENADOR`, `ADMIN`
- devoluções, duplicidades e pós-liquidação

#### `/tesouraria/despesas`

- perfis: `TESOUREIRO`, `ADMIN`
- despesas e resultado mensal

#### `/tesouraria/confirmacoes`

- tela implementada
- hoje bloqueada na camada de acesso do frontend
- não considerar disponível para rotina operacional

### Financeiro > Outras rotas

#### `/importacao`

- perfis: `ADMIN`, `COORDENADOR`
- importação de arquivo retorno
- fluxo atual:
  - upload
  - prévia `dry-run`
  - confirmar ou cancelar
  - histórico e reprocessamento

#### `/renovacao-ciclos`

- perfis: `ADMIN`, `TESOUREIRO`
- dashboard de competência, retorno e monitoramento de ciclos

#### `/relatorios`

- perfis: `ADMIN`
- exportações e visão administrativa

### Administração

#### `/configuracoes/usuarios`

- perfis: `ADMIN`, `COORDENADOR`
- gestão de acessos internos
- inclui:
  - ativação e desativação
  - perfis
  - redefinição de senha
  - redistribuição de carteira ao remover ou desativar agente

#### `/configuracoes/comissoes`

- perfis: `ADMIN`, `COORDENADOR`
- comissão global e overrides por agente

### Aliases mantidos por compatibilidade

#### `/tesouraria/inadimplentes`

- alias de `/tesouraria/baixa-manual`

#### `/tesouraria/liquidacao`

- alias de `/tesouraria/liquidacoes`

#### `/tesouraria/devolucao`

- alias de `/tesouraria/devolucoes`

## Mapa rápido por perfil

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
- `/tesouraria/pagamentos`
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
- `/associados/novo`

### `COORDENADOR`

- `/dashboard`
- `/analise`
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
- `/associados/novo`

### `TESOUREIRO`

- `/tesouraria`
- `/tesouraria/pagamentos`
- `/tesouraria/refinanciamentos`
- `/tesouraria/baixa-manual`
- `/tesouraria/liquidacoes`
- `/tesouraria/devolucoes`
- `/tesouraria/despesas`
- `/renovacao-ciclos`
- `/associados/[id]`

## Pontos de atenção atuais

- `/tesouraria/confirmacoes` existe no código, mas continua bloqueada para navegação
- `/pagamentos` e `/renovacoes` são rotas legadas, não telas finais
- a importação agora depende de confirmação explícita; qualquer runbook antigo que assuma processamento automático está desatualizado
- a gestão de usuários agora tem redistribuição obrigatória de carteira para agente
- pagamento manual precisa ser interpretado corretamente entre “conta para ciclo” e “quitado fora do ciclo”
- saneamentos de março/2026 e novembro/2025 devem respeitar essa distinção

## Fontes de verdade para manutenção futura

Sempre revisar este documento junto com:

- [navigation.ts](/mnt/d/apps/abasev2/abasev2/apps/web/src/lib/navigation.ts)
- [use-permissions.ts](/mnt/d/apps/abasev2/abasev2/apps/web/src/hooks/use-permissions.ts)
- [page.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/app/(dashboard)/importacao/page.tsx)
- [page.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/app/(dashboard)/configuracoes/usuarios/page.tsx)
- [views.py](/mnt/d/apps/abasev2/abasev2/backend/apps/importacao/views.py)
- [views.py](/mnt/d/apps/abasev2/abasev2/backend/apps/accounts/views.py)

## Regra de manutenção deste documento

Atualizar este arquivo sempre que houver qualquer uma destas mudanças:

- nova rota pública ou de dashboard
- mudança de permissão por perfil
- alteração de fluxo entre agente, análise, coordenação e tesouraria
- mudança relevante na importação de retorno
- mudança relevante na lógica de ciclos, parcelas ou pagamento manual
- inclusão de nova rotina administrativa ou operacional
