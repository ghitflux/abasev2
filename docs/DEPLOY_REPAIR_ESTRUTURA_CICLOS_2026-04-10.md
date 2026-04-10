# Deploy: Reparo de Estrutura dos Ciclos

## Objetivo
- Corrigir contratos em que `04/2026` ficou isolado gerando um ciclo final indevido.
- Garantir que ciclo concluído/renovado só exista com `3` parcelas resolvidas.
- Evitar rebuild global cego no servidor.

## Regra funcional aplicada
- `abril/2026` não pode ficar sozinho abrindo `ciclo 3`.
- O mês de `abril/2026` deve voltar para o ciclo anterior quando ele for apenas continuação do ciclo vigente.
- `ciclo_renovado` e `fechado` só podem permanecer se o ciclo tiver `3` parcelas resolvidas.
- Quando o `ciclo 1` não tiver `3` parcelas resolvidas válidas, ele deixa de ser tratado como concluído e passa para `pendencia`.

## Script criado
- [repair_cycle_structure_server.sh](/mnt/d/apps/abasev2/abasev2/scripts/repair_cycle_structure_server.sh)

## O que o script faz
1. Roda `migrate`
2. Executa `repair_trailing_preview_cycles` em loop até zerar remanescentes
3. Executa `repair_incomplete_cycle_one` em loop até zerar remanescentes
4. Faz conferência final dos dois recortes
5. Executa `manage.py check`

## Comando de execução no servidor
```bash
bash scripts/repair_cycle_structure_server.sh
```

## Validação local executada
- `apps.contratos.tests.test_trailing_preview_cycle_repair`: `OK`
- `apps.contratos.tests.test_incomplete_cycle_one_repair`: `OK`
- `python manage.py check`: `OK`

## Resultado obtido localmente
### Reparo de abril isolado
- primeira passada:
  - `129` contratos corrigidos
  - `969` parcelas reorganizadas
  - `129` ciclos extras soft-deletados
  - `13` remanescentes
- segunda passada:
  - `13` contratos corrigidos
  - `65` parcelas reorganizadas
  - `13` ciclos extras soft-deletados
  - `0` remanescentes

### Reparo de ciclo 1 concluído incompleto
- `26` contratos tratados
- `26` rebaixados para `pendencia`
- `0` remanescentes inválidos

## Estado final esperado pós-deploy
- `remaining_trailing_preview_candidates: 0`
- `remaining_invalid_completed_cycle_one: 0`

## Conferência manual recomendada
- Validar contratos que antes exibiam `abril/2026` sozinho como ciclo final
- Conferir que o ciclo mais recente agora contém `abril/2026` como continuação do ciclo vigente
- Conferir que contratos com `ciclo 1` concluído seguem com `3` parcelas resolvidas
- Conferir que contratos sem `3` resolvidas não aparecem mais como ciclo concluído
