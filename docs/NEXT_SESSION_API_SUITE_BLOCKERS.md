# Próxima Sessão: Fechamento da Suíte de APIs

## Objetivo
Fechar os bloqueios restantes da suíte completa de APIs e liberar a validação final para deploy oficial.

## Estado Atual
- Suíte completa de APIs: `7 falhas`, `1 erro`, `1 teste ignorado`.
- Escopo restante: `accounts`, `contratos`, `importacao`, `refinanciamento` e `tesouraria`.

## Critério de Aceite
- Rodar a suíte completa das APIs sem falhas.
- Confirmar que os fluxos abaixo permanecem verdes:
  - importação de retorno com associado `importado`
  - dashboard `/analise` com exclusão e isolamento entre analistas
  - refinanciamento com e sem termo
  - resultado mensal da tesouraria

## Ordem de Ataque
1. Corrigir o erro de `accounts` com `--keepdb`.
2. Fechar os desvios de `refinanciamento`.
3. Ajustar cálculo de `tesouraria`.
4. Corrigir rebuild de `contratos` duplicados.
5. Corrigir reconciliação Maristela em `importacao`.
6. Rerodar a suíte completa e registrar resultado.

## Bloqueios Restantes

### 1. `accounts`: tabelas legadas quebram com `--keepdb`
- Arquivo: [backend/apps/accounts/tests/test_legacy_passwords.py](/mnt/d/apps/abasev2/abasev2/backend/apps/accounts/tests/test_legacy_passwords.py)
- Sintoma: `Table 'users' already exists`.
- Causa provável: `setUpTestData` cria `users`, `roles` e `role_user` sem limpar estado prévio.
- Ajuste esperado:
  - usar `DROP TABLE IF EXISTS` na ordem correta antes do `CREATE TABLE`, ou
  - tornar a criação idempotente e limpar os dados antes dos inserts.
- Validação:
  - rerodar o teste isolado com `--keepdb`.

### 2. `refinanciamento`: mensagem de bloqueio por CPF divergente
- Arquivo: [backend/apps/refinanciamento/strategies.py](/mnt/d/apps/abasev2/abasev2/backend/apps/refinanciamento/strategies.py)
- Sintoma: retorno atual fala `CPF já possui renovação em andamento.`
- Esperado pela suíte: mensagem contendo `CPF já possui refinanciamento ativo`.
- Ajuste esperado:
  - alinhar o texto retornado pela estratégia de elegibilidade.

### 3. `refinanciamento`: fluxo legado sem termo não conclui
- Arquivo: [backend/apps/refinanciamento/services.py](/mnt/d/apps/abasev2/abasev2/backend/apps/refinanciamento/services.py)
- Teste afetado: [backend/apps/tesouraria/tests/test_fluxo_completo.py](/mnt/d/apps/abasev2/abasev2/backend/apps/tesouraria/tests/test_fluxo_completo.py)
- Sintoma:
  - `solicitar/` sem termo já passa no caso legado.
  - `aprovar/` ainda responde `Somente renovações aprovadas pela análise podem seguir para a tesouraria.`
- Esperado pela suíte:
  - coordenação consegue aprovar esse fluxo legado sem termo;
  - refinanciamento fica `concluido`;
  - `ciclo_destino` é criado;
  - depois `efetivar/` continua funcionando.
- Ajuste esperado:
  - suportar explicitamente o ramo legado sem termo dentro de `aprovar`;
  - revisar também a compatibilidade de `efetivar` com esse status.

### 4. `refinanciamento`: reenvio de termo reaproveita o mesmo ID, mas a nota final diverge
- Arquivo: [backend/apps/refinanciamento/services.py](/mnt/d/apps/abasev2/abasev2/backend/apps/refinanciamento/services.py)
- Teste afetado: [backend/apps/refinanciamento/tests/test_refinanciamento_pagamentos.py](/mnt/d/apps/abasev2/abasev2/backend/apps/refinanciamento/tests/test_refinanciamento_pagamentos.py)
- Estado atual:
  - o mesmo refinanciamento já é reaproveitado corretamente;
  - a nota de coordenação continua `Revisar assinatura do termo.`
- Esperado pela suíte:
  - `coordenador_note == "Encaminhado para liquidacao"`
- Ponto objetivo para fechar:
  - definir se o reenvio deve preservar a nota anterior ou transicionar o mesmo registro para a nota/status esperados pela fila final.

### 5. `tesouraria`: pagamento operacional está inflado
- Arquivo: [backend/apps/tesouraria/services.py](/mnt/d/apps/abasev2/abasev2/backend/apps/tesouraria/services.py)
- Testes afetados: [backend/apps/tesouraria/tests/test_despesas.py](/mnt/d/apps/abasev2/abasev2/backend/apps/tesouraria/tests/test_despesas.py)
- Sintoma:
  - esperado `45.00`, atual `120.00`
  - esperado `60.00`, atual `130.00`
- Causa provável:
  - `_resolve_pagamento_operacional_context` está usando `contract.comissao_agente`;
  - esse campo é recalculado no `save()` do contrato e não representa o valor esperado pelos testes.
- Ajuste esperado:
  - derivar `valor_agente` da fonte correta para `payment_kind="contrato_inicial"`;
  - não depender cegamente do valor persistido atual em `comissao_agente`.

### 6. `contratos`: repair de duplicidade reconstrói meses errados
- Arquivos:
  - [backend/apps/contratos/duplicate_billing.py](/mnt/d/apps/abasev2/abasev2/backend/apps/contratos/duplicate_billing.py)
  - [backend/apps/contratos/cycle_rebuild.py](/mnt/d/apps/abasev2/abasev2/backend/apps/contratos/cycle_rebuild.py)
- Teste afetado: [backend/apps/contratos/tests/test_duplicate_billing.py](/mnt/d/apps/abasev2/abasev2/backend/apps/contratos/tests/test_duplicate_billing.py)
- Sintoma:
  - esperado ciclo 1: `2025-10`, `2025-11`, `2025-12`
  - atual: `2025-10`, `2025-12`, `2026-01`
- Hipótese de correção:
  - o rebuild está priorizando referências do contrato duplicado operacional;
  - precisa respeitar a composição correta do ciclo legado efetivado ao mesclar os contratos.

### 7. `importacao`: reconciliação Maristela mantém parcela de março após baixa manual
- Arquivos:
  - [backend/apps/importacao/maristela_reconciliation.py](/mnt/d/apps/abasev2/abasev2/backend/apps/importacao/maristela_reconciliation.py)
  - [backend/apps/importacao/tests/test_reconcile_maristela_sheet.py](/mnt/d/apps/abasev2/abasev2/backend/apps/importacao/tests/test_reconcile_maristela_sheet.py)
- Sintoma:
  - a `BaixaManual` é criada;
  - a `Parcela` de `2026-03-01` continua existindo depois do rebuild.
- Esperado pela suíte:
  - março deve sair da malha de parcelas e ficar representado só pela baixa manual.
- Hipótese de correção:
  - o rebuild está rematerializando a referência em vez de tratá-la como competência já regularizada fora do ciclo.

## Comandos de Validação da Próxima Sessão
```bash
docker compose run --rm backend-tools python manage.py test --keepdb apps.accounts.tests.test_legacy_passwords -v 2
docker compose run --rm backend-tools python manage.py test apps.refinanciamento.tests.test_refinanciamento_pagamentos apps.tesouraria.tests.test_fluxo_completo -v 2
docker compose run --rm backend-tools python manage.py test apps.tesouraria.tests.test_despesas -v 2
docker compose run --rm backend-tools python manage.py test apps.contratos.tests.test_duplicate_billing apps.importacao.tests.test_reconcile_maristela_sheet -v 2
docker compose run --rm backend-tools python manage.py test --keepdb apps.accounts apps.associados apps.contratos apps.esteira apps.financeiro apps.importacao apps.refinanciamento apps.relatorios apps.tesouraria -v 2
```

## Encerramento da Sessão
- Atualizar este arquivo com os resultados dos reruns.
- Só seguir para deploy oficial depois da suíte completa verde.
