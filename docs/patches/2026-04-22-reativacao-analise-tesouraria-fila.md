# Patch 2026-04-22: Reativacao — Secao de Analise e Fila da Tesouraria

## Contexto

Apos a sessao anterior (reativacao + anexos + remocao de filas), tres problemas
foram identificados ao testar o fluxo completo de reativacao da Raquel Pereira
(associado ID 189):

1. **Reativacao nao caia na secao "Contratos para Reativacao" da analise** —
   aparecia apenas em "Ver todos", sem passar pelo crivo especifico de reativacoes.

2. **Multiplas linhas antigas de reativacao apareciam na tesouraria** — contratos
   de reativacoes anteriores (ja cancelados) eram exibidos na secao "Reativacoes"
   junto com o contrato atual pendente.

3. **Remover linha antiga da fila de cancelados cancelava a reativacao atual** —
   ao clicar em "Remover da fila" em um contrato antigo ja cancelado, o servico
   localizava e cancelava o contrato mais recente pendente (o atual), fazendo
   a esteira desaparecer completamente.

4. **Item removido da lista de cancelados nao desaparecia da view** — apos a
   correcao do ponto 3, o contrato antigo continuava visivel porque faltava o
   `soft_delete` especifico sobre ele.

---

## Arquivos alterados

- [backend/apps/esteira/analise_services.py](../../backend/apps/esteira/analise_services.py)
- [backend/apps/tesouraria/services.py](../../backend/apps/tesouraria/services.py)

---

## Diagnostico por problema

### Problema 1 — Reativacao nao aparecia em "Contratos para Reativacao"

**Causa:** A secao `contratos_reativacao` em `AnaliseService.fila_queryset` excluia
itens com `resolved_pendencias_count > 0`. A Raquel tinha uma pendencia resolvida
de um ciclo anterior, o que a jogava para fora da secao mesmo com uma nova
reativacao ativa.

```python
# analise_services.py — diagnostico via shell
# has_pending_reactivation_contract: True
# has_open_pendencia: False
# has_received_reupload: False
# resolved_pendencias_count: 1  ← excluia incorretamente
```

**Regra:** O `resolved_pendencias_count > 0` serve para rotear contratos novos
para "Pendencias corrigidas". Para reativacoes, pendencias antigas de ciclos
anteriores nao devem interferir na triagem atual.

### Problema 2 — Contratos antigos cancelados na secao "Reativacoes" da tesouraria

**Causa:** `listar_contratos_pendentes` incluia contratos com `status=CANCELADO`
via segunda condicao de OR:

```python
| (
    Q(status__in=[Contrato.Status.CANCELADO, Contrato.Status.ENCERRADO])
    & Q(associado__esteira_item__deleted_at__isnull=True)
)
```

Essa condicao e intencional para rastreabilidade historica, mas quando combinada
ao filtro `origem_operacional=reativacao`, trazia todas as tentativas anteriores
(ja canceladas) do mesmo associado.

### Problema 3 — Remocao de contrato antigo cancelava o pendente atual

**Causa:** `excluir_contrato_operacional` recebia o ID do contrato antigo
(ex: Contrato 754, `status=cancelado`). O metodo:

1. `_is_pending_reactivation_contract(contrato_754)` → `False` (ja cancelado)
2. Caia no `else` → chamava `EsteiraService.remover_fila_operacional`
3. `remover_fila_operacional` localizava `_pending_reactivation_contract` → Contrato 780
4. Cancelava e soft_deletava o Contrato 780 (o atual pendente)
5. Fechava a esteira e revertia o associado para `INATIVO`

Resultado: a reativacao atual desaparecia completamente.

**Restauracao manual executada no servidor (producao):**

```python
# Contrato 780
Contrato.all_objects.filter(pk=780).update(
    deleted_at=None, status='em_analise',
    cancelamento_tipo='', cancelamento_motivo='', cancelado_em=None,
    updated_at=now,
)
# EsteiraItem
EsteiraItem.all_objects.filter(pk=item.pk).update(
    deleted_at=None, etapa_atual=EsteiraItem.Etapa.TESOURARIA,
    status=EsteiraItem.Situacao.AGUARDANDO, concluido_em=None,
    updated_at=now,
)
# Associado
Associado.objects.filter(pk=189).update(status='em_analise', updated_at=now)
```

### Problema 4 — Item continuava visivel apos remocao

**Causa:** O branch de guarda adicionado para o problema 3 registrava a acao
e retornava sem fazer `soft_delete` do contrato antigo especifico selecionado.

---

## Correcoes aplicadas

### `backend/apps/esteira/analise_services.py`

Removido `resolved_pendencias_count__gt=0` da exclusao da secao
`contratos_reativacao`:

```python
# Antes
if secao == "contratos_reativacao":
    return queryset.filter(
        etapa_atual=EsteiraItem.Etapa.ANALISE,
        has_pending_reactivation_contract=True,
    ).exclude(
        Q(has_open_pendencia=True)
        | Q(has_received_reupload=True)
        | Q(resolved_pendencias_count__gt=0)   # ← removido
        | Q(associado__status__in=[...])
    )

# Depois
if secao == "contratos_reativacao":
    return queryset.filter(
        etapa_atual=EsteiraItem.Etapa.ANALISE,
        has_pending_reactivation_contract=True,
    ).exclude(
        Q(has_open_pendencia=True)
        | Q(has_received_reupload=True)
        | Q(associado__status__in=[...])
    )
```

### `backend/apps/tesouraria/services.py`

**Fix 1 — Query da secao Reativacoes:**

```python
# listar_contratos_pendentes
if origem_operacional == Contrato.OrigemOperacional.REATIVACAO:
    queryset = queryset.exclude(
        status__in=[Contrato.Status.CANCELADO, Contrato.Status.ENCERRADO]
    )
```

**Fix 2 — Guarda em `excluir_contrato_operacional`:**

```python
# Contrato ja cancelado/encerrado: nao fechar a esteira caso ainda exista
# uma reativacao pendente ativa (evita cancelar o contrato mais recente).
if contrato.status in [Contrato.Status.CANCELADO, Contrato.Status.ENCERRADO]:
    pending = EsteiraService._pending_reactivation_contract(esteira_item)
    if pending is not None:
        # Oculta o contrato antigo da fila sem tocar na esteira nem no pendente.
        soft_delete_contract_tree(contrato)
        TesourariaService._registrar_remocao_contrato_sem_fechar_esteira(
            esteira_item, user=user, observacao=observacao,
        )
        return contrato
    # Sem reativacao pendente: fecha a esteira normalmente
    soft_delete_contract_tree(contrato)
    EsteiraService.remover_fila_operacional(esteira_item, user, observacao=observacao)
    return contrato
```

---

## Commits

| Hash | Descricao |
|------|-----------|
| `ce63b32` | fix: reativacao aparece em contratos_reativacao mesmo com pendencia antiga resolvida |
| `fc5c2ff` | fix: tesouraria reativacoes nao exibe contratos ja cancelados; remove protege esteira ativa |
| `3da86eb` | fix: soft_delete do contrato antigo ao remover da fila de cancelados com reativacao pendente |

---

## Sem migracao

Nenhum modelo foi alterado. Nao requer `manage.py migrate`.

---

## Validacao local executada

### Shell com savepoint (nao persistido)

```python
# Confirmado em producao via shell + savepoint:
# - Remocao do Contrato 754 (cancelado antigo):
#   Contrato 754 apos remocao: deleted_at=2026-04-22 21:21:44  ← some da lista
#   Contrato 780 (pendente): status=em_analise deleted_at=None  ← intacto
#   Esteira: etapa=tesouraria deleted_at=None                   ← intacta
# Rollback executado.
```

### Teste de fila analise

```python
AnaliseService.fila_queryset('contratos_reativacao', admin)
# Total: 1  |  Raquel na secao? True
```

### Teste de fila tesouraria

```python
TesourariaService.listar_contratos_pendentes(origem_operacional='reativacao')
# Total reativacoes pendentes: 1
# Contratos Raquel na fila: 1  → Contrato 780
# Contratos cancelados da Raquel (4) nao aparecem
```

---

## Comportamento esperado apos o patch

- Associado reativado cai na secao **"Contratos para Reativacao"** da analise,
  mesmo que tenha pendencias resolvidas de ciclos anteriores.
- Na tesouraria, a secao **"Reativacoes"** exibe apenas o contrato pendente atual,
  sem listar tentativas anteriores ja canceladas.
- Ao clicar em **"Remover da fila"** em um contrato ja cancelado (secao Cancelados)
  enquanto existe uma reativacao pendente ativa:
  - O contrato antigo e soft_deleted e some da lista.
  - A reativacao atual e a esteira permanecem intactas.
- Ao clicar em **"Remover da fila"** em um contrato ja cancelado sem reativacao
  pendente, a esteira e fechada normalmente.

---

## Deploy executado

```bash
# analise_services — commit ce63b32
git pull --ff-only origin abaseprod
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml build --no-cache backend celery
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml up -d --force-recreate --no-deps backend celery

# tesouraria — commits fc5c2ff e 3da86eb (mesmo procedimento, 2x)
```

Resultado: `System check identified no issues (0 silenced).` em todas as execucoes.
