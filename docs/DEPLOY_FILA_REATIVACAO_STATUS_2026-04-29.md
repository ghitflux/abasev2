# Deploy 2026-04-29 - fila operacional e status reativacao

## Commits

- `ad83099` — fix: reativacao nao mostra apto_a_renovar com pagamentos do contrato anterior
- `dc591e5` — fix: remover_fila para contratos cancelados com esteira CONCLUIDO

## Problema 1 — Reativação marcada como "apto a renovar"

### Sintoma

Associado com contrato de reativação aparecia como `apto_a_renovar` na
interface, mesmo sem nenhuma parcela paga no novo contrato.

### Causa raiz

`_query_pagamentos` em `cycle_projection.py` é associado-wide: retorna
todos os `PagamentoMensalidade` do associado independente do contrato de
origem. Para a Jarlene (CPF 02500011364), o contrato anterior
(CTR-20251128082036-F8TYG, cancelado) tinha três pagamentos descontados
em 2025-12, 2026-01 e 2026-02.

A função `_seed_reference` escolhia `min(candidates)` = 2025-12 como
âncora do ciclo da reativação. Com esses três pagamentos formando um
ciclo completo de 3 meses e `paid_count=3 >= threshold=2`, a projeção
retornava `cycle_status=APTO_A_RENOVAR`. As parcelas `em_previsao` do
novo ciclo (2026-04/05/06) eram invisíveis à projeção por não passarem
por `_merge_financial_references`.

### Correção

`backend/apps/contratos/cycle_projection.py` — função `_seed_reference`.

Após calcular `seed = min(candidates)`, para contratos de reativação o
seed é limitado ao início do mês de `auxilio_liberado_em`. Pagamentos
anteriores ao auxílio ficam em `movimentos_financeiros_avulsos` e não
formam ciclo.

```python
if candidates:
    seed = min(candidates)
    if (
        str(getattr(contrato, "origem_operacional", "") or "") == "reativacao"
        and contrato.auxilio_liberado_em is not None
    ):
        reativacao_start = _month_start(contrato.auxilio_liberado_em)
        if reativacao_start is not None and seed < reativacao_start:
            seed = reativacao_start
    return seed
```

### Validação

Após o deploy, a projeção da Jarlene passou a mostrar:

```
status_renovacao: (vazio)
ciclo numero=2 status=aberto
  parcela ref=2026-04 status=em_previsao
  parcela ref=2026-05 status=em_previsao
  parcela ref=2026-06 status=em_previsao
```

---

## Problema 2 — "Remover da fila" bloqueado com erro

### Sintoma

Ao clicar em "Remover da fila" na tesouraria (tanto em Novos Contratos
quanto em Cancelados / Desistentes), a operação falhava com:

> Itens concluídos não fazem parte da fila operacional.

### Causa raiz

`excluir_contrato_operacional` em `tesouraria/services.py` sempre
delegava para `EsteiraService.remover_fila_operacional`, que rejeita
itens com `etapa_atual == CONCLUIDO`. Isso ocorre quando uma reativação
já foi efetivada e aprovada: a esteira fica CONCLUIDA mas o item ainda
aparece na lista da tesouraria.

Havia dois caminhos sem o check:

1. **Caminho geral** (não cancelado, não reativação pendente) — corrigido
   no commit `ad83099`.
2. **Caminho CANCELADO/ENCERRADO sem reativação pendente** — não coberto
   pelo fix anterior; corrigido no commit `dc591e5`.

### Correção

`backend/apps/tesouraria/services.py` — função `excluir_contrato_operacional`.

**Commit ad83099** — caminho geral (antes da chamada final a
`remover_fila_operacional`):

```python
# Esteira já concluída: apenas oculta o item da fila via soft-delete.
if esteira_item.etapa_atual == EsteiraItem.Etapa.CONCLUIDO:
    esteira_item.soft_delete()
    contrato.refresh_from_db()
    return contrato
```

**Commit dc591e5** — caminho CANCELADO/ENCERRADO (dentro do `if contrato.status in [CANCELADO, ENCERRADO]`):

```python
# Sem reativacao pendente: fecha a esteira normalmente
soft_delete_contract_tree(contrato)
# Esteira já concluída: apenas oculta o item sem alterar seu estado.
if esteira_item.etapa_atual == EsteiraItem.Etapa.CONCLUIDO:
    esteira_item.soft_delete()
    return contrato
EsteiraService.remover_fila_operacional(
    esteira_item,
    user,
    observacao=observacao,
)
return contrato
```

### Comportamento esperado após a correção

- Contrato com esteira CONCLUIDA: soft-delete do `EsteiraItem`, item
  some da lista (filtro `deleted_at__isnull=True`). Estado do associado
  e do contrato não são alterados.
- Contrato com esteira em estado ativo (APROVADO, PENDENCIADO etc.):
  fluxo normal via `remover_fila_operacional`.

---

## Arquivos alterados

| Arquivo | Motivo |
|---|---|
| `backend/apps/contratos/cycle_projection.py` | Clampeia seed da reativação em `auxilio_liberado_em` |
| `backend/apps/tesouraria/services.py` | Soft-delete para esteira CONCLUIDA em ambos os caminhos |

## Sem migrations

Nenhuma migration neste conjunto de correções.
