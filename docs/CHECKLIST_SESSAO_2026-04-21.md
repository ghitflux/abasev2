# Checklist da Sessão 2026-04-21

## Escopo consolidado

- [x] Universalização da lógica de ciclos, renovação, warnings e esteira pós-edição.
- [x] Correções de detalhes do associado, ciclos, anexos e comprovantes trocados.
- [x] Ajustes de interface no detalhe do associado.
- [x] Correções do módulo de importação, prévia, aptos a renovar, busca e exportação.
- [x] Revisões do modo editor avançado, sincronização de status e desempenho pós-salvamento.
- [x] Implementação de reativação de associado inativo com envio para tesouraria.
- [x] Correção de refinanciamento efetivado fantasma após edição administrativa.
- [x] Reinícios operacionais dos containers locais durante a sessão.

## Ciclos, renovação e editor avançado

- [x] Unificada a projeção manual para que editor avançado, detalhe do associado, renovação e demais módulos usem a mesma verdade persistida.
- [x] `layout_bucket` persistido passou a ser tratado como fonte de verdade para ciclos, meses não pagos e movimentos financeiros avulsos.
- [x] Garantido que `nao_descontado` salvo dentro do ciclo permaneça no ciclo em todos os módulos.
- [x] Corrigida a regra de duplicidade de competência no `save-all`: a última ocorrência enviada passa a vencer e as anteriores são normalizadas.
- [x] Ciclo técnico vazio deixou de aparecer como ciclo de negócio quando só existem movimentos fora do ciclo.
- [x] Correção da fila `Aptos a renovar` para contratos com refinanciamento operacional ativo.
- [x] Edição de ciclo deixou de mover associado automaticamente para `contratos concluídos`.
- [x] `concluido_em` passou a depender de transição explícita de esteira, sem ser sobrescrito por edição de ciclo.
- [x] Warnings estruturados passaram a ser corretivos e não bloqueantes para salvar ciclo e mover etapa.
- [x] Casos de referência tratados na sessão:
- [x] AIRTON QUARESMA DE SOUZA: ciclo concluído voltou a ser considerado para aptidão de renovação.
- [x] RAQUEL PEREIRA DE OLIVEIRA: ciclo concluído voltou a ser considerado para aptidão de renovação.
- [x] UBIRAJARA DE SOUSA ROCHA: repetição de fevereiro deixou de reaparecer após salvar.
- [x] MARIA DA CONCEICAO CAMPELO LIMA: março salvo como não descontado deixou de voltar para previsão.
- [x] MARIA DE JESUS SANTANA COSTA: parcelas avulsas fora do ciclo deixaram de formar ciclo visível falso.

## Detalhes do associado, ciclos e anexos

- [x] Corrigida a projeção de anexos dos ciclos para buscar comprovantes por contrato, ciclo e refinanciamento.
- [x] Ajustado o vínculo de anexos órfãos para o ciclo visível correto.
- [x] Corrigido o caso em que alguns anexos não apareciam em detalhes do associado e em ciclos.
- [x] Corrigida a exibição de parcelas não descontadas que estavam sumindo em alguns associados.
- [x] Separados corretamente os comprovantes de efetivação dos comprovantes de renovação/refinanciamento.
- [x] Caso de referência usado na auditoria funcional: Ubirajara.

## Interface do detalhe do associado

- [x] Nome do associado no topo passou a ter ação de cópia.
- [x] CPF passou a usar snippet de cópia.
- [x] Matrícula passou a usar snippet de cópia.
- [x] Nome do agente foi adicionado no topo do detalhe do associado.
- [x] Ajuste aplicado tanto na página completa quanto no modal de detalhes.

## Importação e prévia da importação

- [x] Adicionado card de `Ficarão aptos a renovar` na prévia da importação.
- [x] Card passou a abrir modal/tabela com os associados afetados.
- [x] Corrigido o `dry-run` da importação para simular aptidão real de renovação.
- [x] Prévia do arquivo `Relatorio_D2102-03-2026.txt` deixou de subcontar aptos.
- [x] Contagem corrigida de `6` para `65` no cenário local validado da competência de março.
- [x] Corrigido o fechamento da prévia para cancelar upload pendente de forma idempotente.
- [x] `Cancelar`, `X` e fechamento passaram a compartilhar a mesma rotina de cancelamento.
- [x] Corrigido o proxy do frontend para respostas `204/205/304` sem body no cancelamento da prévia.
- [x] Corrigido warning de acessibilidade de `DialogContent` sem descrição no modal da prévia.
- [x] Adicionada busca visível dentro do modal `Ficarão aptos a renovar`.
- [x] Toolbar de busca/exportação do modal ficou fixa no topo durante o scroll.
- [x] Adicionada exportação do conteúdo filtrado em `CSV`, `XLS` e `PDF`.

## Editor avançado: sincronização e desempenho

- [x] Corrigida a permanência indevida da tag `Apto para Renovação` após edição manual da renovação.
- [x] Cache da fila de aptos passou a ser invalidado antes da sincronização final de status do associado.
- [x] Caso tratado na sessão: CPF `09945431315`, que voltou para `ativo` após desativar a renovação.
- [x] Reduzido o tempo percebido após `Salvar tudo` no editor avançado.
- [x] O payload retornado pelo `save-all` passou a ser aplicado imediatamente no cache do editor.
- [x] Refetch de detalhe e histórico passou a rodar em background, sem bloquear o fechamento do modal.
- [x] Warnings já conhecidos deixaram de disparar toast repetido a cada salvamento.
- [x] Corrigido o diálogo de confirmação para não fechar sozinho quando a operação falha.
- [x] O fechamento do diálogo passou a ficar sob controle do chamador.

## Reativação de associado e tesouraria

- [x] Implementado fluxo de reativação de associado inativo a partir do detalhe do associado.
- [x] Reativação passou a criar um novo contrato, preservando o histórico anterior.
- [x] Adicionado marcador de origem operacional `reativacao` no contrato.
- [x] Reaproveitamento do `EsteiraItem` com envio direto para `tesouraria/aguardando`.
- [x] Criação da seção `Reativações` em `Novos Contratos` na tesouraria.
- [x] Adicionado botão `Reativar associado` no detalhe do associado para `ADMIN` e `COORDENADOR`.
- [x] Backend centralizou o cálculo financeiro da reativação com a mesma regra da etapa 5 do cadastro.
- [x] Fluxo passou a aceitar atualização de anexos no mesmo padrão do cadastro/edição.
- [x] Criado endpoint `POST /api/v1/associados/:id/reativar/`.
- [x] Tesouraria passou a aceitar filtro por `origem_operacional`.

## Renovação fantasma após edição administrativa

- [x] Identificada a causa do refinanciamento fantasma: o `save-all` do editor ainda aceitava gravar `status=efetivado` diretamente.
- [x] Bloqueada no backend a mudança de status da renovação pelo editor avançado.
- [x] A efetivação voltou a ficar restrita à tesouraria, com comprovantes e materialização real.
- [x] O editor deixou de exibir seletor editável de status da renovação e passou a orientar para `Enviar para etapa` e tesouraria.
- [x] A lista de `tesouraria/refinanciamentos` passou a ignorar `efetivado` fantasma sem `executado_em`, sem `data_ativacao_ciclo` e sem materialização.
- [x] Reparo operacional aplicado em refinanciamentos contaminados com `repair_renewal_alignment --apply --competencia 2026-04`.
- [x] Caso corrigido na sessão:
- [x] CPF `24005126391`: refinanciamento `#1585` saiu de `efetivado` fantasma e voltou para `apto_a_renovar`.
- [x] CPF `24005126391`: refinanciamento legítimo `#127` permaneceu `efetivado`.

## Containers e operação local

- [x] Containers locais foram reiniciados ao longo da sessão para carregar correções.
- [x] Backend, frontend, MySQL, Redis e Celery foram revalidados após reinícios.
- [x] Healthcheck do backend foi conferido após reinicialização.

## Validações executadas durante a sessão

- [x] `python -m py_compile` em arquivos backend alterados em múltiplas rodadas.
- [x] `pnpm --filter @abase/web type-check` executado nas rodadas relevantes do frontend.
- [x] Testes focados de backend para ciclos, overrides, refinanciamento, importação e reativação.
- [x] Testes focados de frontend para página do associado, modal de importação e diálogo de confirmação.
- [x] `git diff --check` executado nas rodadas de fechamento.
- [x] Auditorias em banco e shell do container para CPFs e refinanciamentos citados.

## Observações operacionais

- [x] Em alguns testes de frontend o runner de Jest exigiu `--forceExit` por handles abertos no workspace.
- [x] O reparo operacional de refinanciamentos fantasmas identificou resíduos além do caso reportado e aplicou saneamento na competência auditada.
- [x] O checklist acima consolida apenas o que foi tratado, corrigido, ajustado ou validado nesta sessão.
