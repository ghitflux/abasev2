# Plano de Melhorias Web Prioritárias

Atualizado em: 08/04/2026

## 1. Contexto, objetivo e fonte do backlog

Este documento organiza a próxima frente de correções e melhorias da aplicação web com foco em estabilização operacional antes de novas entregas.

O backlog base deste plano foi consolidado a partir de:

- `docs/CHECKLIST_WEB_E2E_POR_FLUXO.md`
- `docs/ROTINAS_POR_PERFIL_E_ROTAS.md`
- stack atual de `admin-overrides`
- comportamento já coberto por testes e fluxos existentes de coordenação, refinanciamento, tesouraria e pagamentos

Objetivo desta rodada:

- corrigir os fluxos críticos com maior impacto operacional
- fechar os pontos que travam uso diário de coordenação, editor admin e financeiro
- transformar o backlog atual em uma fila executável, com critérios de aceite claros

Prioridade fixa desta fase:

1. `Coordenação`
2. `Admin editor completo`
3. `Tesouraria e pagamentos`

Decisões travadas para esta fase:

- o coordenador passa a ter acesso ao modo editor do associado com auditoria completa
- esse acesso será pelo detalhe do associado e pela superfície de override, sem substituir o formulário administrativo tradicional de `/associados/[id]/editar`
- o motivo do override continua obrigatório e toda gravação deve manter trilha de auditoria
- tesouraria e pagamentos permanecem como frente financeira principal de `TESOUREIRO` e `ADMIN`
- atalhos e encaminhamentos vindos da coordenação não devem abrir acesso geral a filas financeiras fora do escopo aprovado

Assunções desta fase:

- o backlog desta rodada será montado apenas a partir do estado atual do repositório e dos roteiros de QA já existentes
- `modo admin editor completo` significa o editor do associado e seus desdobramentos operacionais e financeiros
- gestão administrativa geral de usuários e configurações fica fora desta frente, salvo impactos diretos de permissão
- o acesso ampliado do coordenador vale para o editor por override, não para substituir a edição cadastral tradicional

## 2. Matriz de priorização

| Frente | Item | Sintoma | Impacto | Correção esperada | Critério de aceite | Owner | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Coordenação | Fluxo pós-análise para coordenação | renovação pode perder consistência entre análise, coordenação e tesouraria | quebra do fluxo principal de renovação | garantir leitura apenas de itens pós-análise e envio correto para a fila seguinte | item aprovado no analista aparece na coordenação e, ao aprovar, entra somente na fila correta da tesouraria | Backend + Frontend | Pendente |
| Coordenação | Tela de refinanciamento | aprovação, devolução, anexos, aprovação em massa e liquidação precisam operar sem desvios | fila trava ou segue para destino incorreto | revisar ações e estados da tela principal da coordenação | aprovação individual, devolução, aprovação em massa e encaminhamento para liquidação funcionam sem salto indevido | Frontend + Backend | Pendente |
| Coordenação | Tela de refinanciados | histórico, filtros e status podem divergir da tesouraria | leitura gerencial perde confiabilidade | alinhar listagem, filtros e histórico com o estado real dos refinanciamentos | coordenação enxerga histórico coerente com origem, status e desdobramento financeiro | Frontend | Pendente |
| Coordenação | Acesso do coordenador ao editor | coordenador hoje não fecha sozinho correções operacionais no detalhe do associado | dependência excessiva de admin para saneamento | liberar o modo editor do associado ao coordenador com auditoria | coordenador acessa o editor, salva com motivo e gera evento auditável | Backend + Frontend | Pendente |
| Admin editor completo | Salvar núcleo do associado e esteira | casos já testados falham ao salvar ou exigem retrabalho | correção operacional fica incompleta | estabilizar gravação de dados centrais e esteira | salvar dados do associado e esteira conclui sem erro e sem regressão de estado | Backend + Frontend | Pendente |
| Admin editor completo | Salvar contrato, ciclos e parcelas | alguns saves deixam ciclo inconsistente ou inativo | risco financeiro e contábil | garantir integridade de contrato, materialização e layout manual | nenhum save-all desativa ciclo/parcela indevidamente e o layout manual permanece refletido no detalhe | Backend | Pendente |
| Admin editor completo | Refinanciamento, documentos e comprovantes | overrides e versionamento ainda precisam fechamento de ponta a ponta | operação perde autonomia para corrigir cadastro e evidências | fechar gravação, versionamento, histórico e reversão com rastreabilidade | histórico mostra ator, motivo, diff e reversão sem apagar evento anterior | Backend + Frontend | Pendente |
| Admin editor completo | Permissão e auditoria do coordenador | novo acesso do coordenador precisa manter governança | risco de edição sem trilha | aplicar mesma regra de auditoria hoje usada pelo admin | toda alteração do coordenador exige motivo, respeita conflito de versão e registra evento | Backend | Pendente |
| Tesouraria e pagamentos | Novos contratos e confirmações | anexos, efetivação e confirmação precisam manter sequência operacional | contrato pode ficar preso ou ser concluído de forma incompleta | revisar dashboard principal e confirmações | contrato pendente pode ser efetivado e confirmado com status refletido no detalhe do associado | Frontend + Backend | Pendente |
| Tesouraria e pagamentos | Renovações na tesouraria | renovação aprovada pela coordenação precisa materializar ciclo corretamente | quebra de renovação financeira | revisar fila, anexos finais e efetivação | somente itens validados pela coordenação entram na fila e a efetivação cria o próximo ciclo corretamente | Backend + Frontend | Pendente |
| Tesouraria e pagamentos | Baixa manual, liquidações e devoluções | estados, permissões e efeitos financeiros podem divergir do esperado | saneamento financeiro fica inseguro | consolidar regras de alteração financeira por subfluxo | cada submódulo aplica apenas o efeito financeiro previsto, sem contaminar parcela, ciclo ou contrato indevidamente | Backend | Pendente |
| Tesouraria e pagamentos | Despesas e visão de pagamentos | filtros, cards e consistência de dados ainda precisam fechamento | leitura financeira diária perde confiabilidade | revisar listagens, totais, filtros e exportações | contadores, filtros e status batem com os dados retornados pela API | Frontend | Pendente |
| Tesouraria e pagamentos | Consistência transversal do detalhe do associado | ações financeiras nem sempre refletem claramente no detalhe | suporte e conferência ficam lentos | garantir que tesouraria reflita corretamente no detalhe do associado | após efetivação, baixa, liquidação ou devolução, o detalhe mostra histórico, anexos e estados corretos | Backend + Frontend | Pendente |

## 3. Frente 1: Coordenação

### Escopo desta frente

- revisar `/coordenacao/refinanciamento` como fila principal de decisão operacional pós-análise
- revisar `/coordenacao/refinanciados` como visão histórica e de acompanhamento
- garantir que coordenação não receba item bruto do agente nem desvie item direto para a fila errada
- incluir acesso do coordenador ao modo editor do associado no detalhe

### Correções prioritárias

- validar anexos e termos da renovação sem exigir retrabalho fora do fluxo
- corrigir aprovação individual para envio consistente à tesouraria
- corrigir devolução para análise com motivo e retorno visível na fila correta
- revisar aprovação em massa para operar somente sobre itens elegíveis
- revisar encaminhamento para liquidação a partir da coordenação sem abrir acesso financeiro geral indevido
- alinhar filtros, status e histórico da tela de refinanciados com o estado real da renovação

### Regras de acesso e permissão

- `COORDENADOR` continua tendo leitura global do detalhe do associado
- `COORDENADOR` passa a acessar também o modo editor do associado no detalhe
- a rota administrativa tradicional de edição cadastral continua separada do editor por override
- nenhuma ação da coordenação deve conceder acesso amplo a filas financeiras fora do fluxo explicitamente permitido

### Critérios de aceite da frente

- renovação aprovada na análise aparece na coordenação e não salta direto para tesouraria
- aprovação da coordenação envia o item somente para a fila correta da tesouraria
- devolução para análise retorna com motivo e histórico
- aprovação em massa ignora itens não elegíveis e informa falhas de forma controlada
- coordenador consegue abrir o detalhe do associado, ativar o editor e salvar com auditoria

## 4. Frente 2: Admin editor completo

### Escopo desta frente

O foco desta frente é o editor completo do associado e seus desdobramentos operacionais e financeiros, sem incluir administração geral de usuários ou configurações.

Blocos cobertos:

- núcleo do associado
- esteira
- contrato
- ciclos e parcelas
- refinanciamento
- documentos e comprovantes
- histórico administrativo e reversão

### Correções prioritárias

- estabilizar o `save-all` para que salvar não falhe em casos já testados pela operação
- impedir qualquer gravação que deixe ciclo inativo, parcela deslocada incorretamente ou contrato financeiramente inconsistente
- preservar layout manual de ciclos após rebuild e reabertura do detalhe
- garantir versionamento de documentos e comprovantes com histórico completo
- garantir reversão como novo evento administrativo, sem apagar o evento original

### Regras de funcionamento

- o editor admin continua sendo uma superfície separada da edição cadastral tradicional
- toda alteração segue com motivo obrigatório e trilha de auditoria
- conflito de versão deve bloquear gravação silenciosa quando houver dado desatualizado
- `ADMIN` e `COORDENADOR` passam a operar sob a mesma regra de auditoria no editor por override

### Critérios de aceite da frente

- todos os blocos do editor salvam com sucesso quando usados isoladamente ou via `save-all`
- nenhuma gravação desativa ciclo ou parcela indevidamente
- contrato, ciclos, parcelas e refinanciamento permanecem coerentes após salvar e recarregar
- documentos e comprovantes podem ser versionados com histórico consultável
- reversão cria novo evento administrativo com ator, motivo, data/hora e diff

## 5. Frente 3: Tesouraria e pagamentos

### Escopo desta frente

Subfluxos cobertos nesta rodada:

- `/tesouraria`
- `/tesouraria/confirmacoes`
- `/tesouraria/refinanciamentos`
- `/tesouraria/pagamentos`
- `/tesouraria/baixa-manual`
- `/tesouraria/liquidacoes`
- `/tesouraria/devolucoes`
- `/tesouraria/despesas`

### Quebra por tipo de ajuste

#### Bugs funcionais

- efetivação de contrato novo com anexos e saída correta da fila
- confirmações de ligação e averbação refletindo o estado real do contrato
- efetivação de renovação materializando corretamente o próximo ciclo
- baixa manual alterando apenas a parcela correta
- liquidação encerrando contrato sem abrir ciclo novo indevido
- devolução registrando histórico sem alterar o que não faz parte da regra

#### Regras de permissão

- frente financeira principal continua restrita a `TESOUREIRO` e `ADMIN`
- coordenação interage por suas próprias telas e gatilhos aprovados, sem ganhar acesso irrestrito à tesouraria
- qualquer exceção operacional deve estar explícita no fluxo, nunca implícita por permissão ampla

#### Ajustes de filtro, estado e consistência

- revisar cards, tabelas, filtros, totais e exportações da visão de pagamentos
- alinhar status e histórico entre tesouraria e detalhe do associado
- garantir que anexos e comprovantes apareçam nos blocos corretos após cada ação financeira

### Critérios de aceite da frente

- novos contratos podem ser efetivados com exigência dos anexos obrigatórios
- confirmações atualizam a situação do contrato sem divergência com o detalhe do associado
- renovações aprovadas pela coordenação entram na fila correta e materializam o ciclo seguinte
- baixa manual, liquidações e devoluções alteram somente os efeitos financeiros previstos
- filtros, contadores e status em pagamentos batem com a resposta da API

## 6. Plano de validação e definição de pronto

### Backend

- estender `test_admin_overrides` para validar permissão do coordenador no editor por override
- validar criação de auditoria para alterações feitas por `COORDENADOR`
- validar integridade de contrato, ciclo e parcela após `save-all`
- validar explicitamente que nenhuma gravação do editor deixa ciclo ou parcela inativos sem intenção declarada

### Frontend

- cobrir acesso do coordenador ao modo editor no detalhe do associado
- validar estados de carregamento, sucesso e erro nos blocos editáveis prioritários
- manter smoke tests das telas prioritárias de coordenação, tesouraria e pagamentos

### E2E e validação manual prioritária

Executar primeiro os cenários pendentes de:

- `/coordenacao/refinanciamento`
- `/coordenacao/refinanciados`
- `/associados/[id]` em modo editor admin
- `/tesouraria`
- `/tesouraria/confirmacoes`
- `/tesouraria/refinanciamentos`
- `/tesouraria/pagamentos`

### Definição de pronto desta fase

- coordenador acessa e salva no editor com auditoria registrada
- admin editor salva associado, contrato, ciclos, arquivos e refinanciamento sem corromper estado financeiro
- ações da coordenação refletem corretamente na fila da tesouraria
- tesouraria e pagamentos apresentam filtros, status e contadores coerentes com os dados retornados
- backlog crítico fica convertido em checklist executável e passível de acompanhamento por owner

## Apêndice A: Mensagem sugerida para o grupo

Pessoal, o foco imediato da próxima rodada será estabilizar os fluxos críticos da operação antes de abrir novas entregas.

- [ ] Prioridade 1: coordenação. Revisar refinanciamento de ponta a ponta, aprovação individual e em massa, devolução para análise, histórico dos refinanciados e acesso do coordenador ao modo editor do associado com auditoria.
- [ ] Prioridade 2: modo admin editor completo. Garantir que o editor salve 100% dos blocos sem quebrar contrato, ciclo, parcela, refinanciamento, documentos, comprovantes ou histórico administrativo.
- [ ] Prioridade 3: tesouraria e pagamentos. Consolidar ajustes no dashboard principal, confirmações, refinanciamentos, baixa manual, liquidações, devoluções, despesas e visão de pagamentos.
- [ ] Validar tudo por checklist e por fluxo real, principalmente nos pontos que impactam decisão operacional, correção cadastral e fechamento financeiro.
- [ ] Atualizar status continuamente com base no que for corrigido, homologado e fechado.
