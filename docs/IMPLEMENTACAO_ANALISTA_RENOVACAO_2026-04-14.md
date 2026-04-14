# Implementação Analista e Contratos para Renovação

Data: 2026-04-14

## Escopo concluído

### Rota: Analista

- [x] Ajustar esteira de status no módulo `dashboard.analise`
- [x] Permitir reprovação pelo analista com exclusão correta do cadastro do associado
- [x] Exibir valor da doação nos detalhes do associado para analista e demais perfis

### Rota: Contratos para Renovação

- [x] Parar de sobrescrever renovações anteriores
- [x] Adicionar filtro por ciclo
- [x] Otimizar a rota para expandir a linha do associado
- [x] Permitir expandir cada renovação e cada parcela

## O que foi alterado

### Esteira do analista

- A ação `reprovar` foi adicionada à etapa `analise:em_andamento`.
- A reprovação reutiliza a mesma exclusão lógica em cascata já validada na esteira:
  - associado
  - esteira
  - documentos
  - issues de documento
  - reuploads
  - árvore contratual operacional
- O dashboard `dashboard.analise` passou a exibir status com leitura mais consistente:
  - etapa operacional
  - situação atual
  - contexto documental

### Valor da doação

- O valor da doação passou a aparecer no diálogo de detalhes do associado.
- O valor também foi exposto no resumo do contrato dentro do histórico de contratos e ciclos.

### Histórico de renovação

- A seleção da renovação operacional ativa foi endurecida para não reutilizar registros já efetivados/concluídos.
- O rebuild de ciclos e a estratégia de elegibilidade agora distinguem:
  - renovação ativa em aberto
  - renovação histórica já efetivada
- Com isso, um novo ciclo apto gera uma nova renovação sem sobrescrever a anterior.

### Auditoria na rota `analise/aptos`

- Foi adicionado filtro por ciclo via `cycle_key`.
- A tabela agora permite expandir a linha do associado.
- A expansão mostra o histórico auditável do associado usando contratos, ciclos e parcelas.
- Os ciclos passaram a ser exibidos em acordeão, facilitando navegação por:
  - ciclo
  - parcelas do ciclo
  - anexos do ciclo

## Arquivos principais

- `backend/apps/esteira/services.py`
- `backend/apps/esteira/views.py`
- `backend/apps/esteira/tests/test_analise.py`
- `backend/apps/contratos/cycle_rebuild.py`
- `backend/apps/refinanciamento/payment_rules.py`
- `backend/apps/refinanciamento/services.py`
- `backend/apps/refinanciamento/tests/test_refinanciamento_pagamentos.py`
- `apps/web/src/app/(dashboard)/analise/page.tsx`
- `apps/web/src/app/(dashboard)/analise/aptos/page.tsx`
- `apps/web/src/components/associados/associado-contracts-overview.tsx`
- `apps/web/src/components/associados/associado-details-dialog.tsx`
- `apps/web/src/components/shared/data-table.tsx`

## Validação executada

- `python -m py_compile` nos arquivos backend alterados
- `git diff --check`
- `npx prettier --check` nos arquivos frontend alterados
- testes backend direcionados no container `abase-v2-backend-1`:
  - `test_reprovar_item_em_analise_remove_cadastro_completo`
  - `test_novo_ciclo_cria_nova_renovacao_sem_sobrescrever_historico_anterior`
  - `test_fluxo_devolucao_de_termo_reaproveita_mesmo_refinanciamento`
  - `test_analise_resumo_refinanciamentos_retorna_cards_operacionais`

## Observação de ambiente

- O `pnpm --filter @abase/web type-check` continua falhando por erro preexistente em `apps/web/src/components/shared/report-export-dialog.tsx`, fora do escopo desta entrega.

---

## Normalização de dados — novos_contratos divergentes (2026-04-14)

### Contexto

Após normalização da esteira, a seção `novos_contratos` continuava exibindo associados com status já efetivados ou com pagamentos cancelados. Duas correções foram aplicadas:

**Correção 1 — 62 associados com pagamento `pago` → normalizados para `ativo`** (já aplicado em produção em sessão anterior).

**Correção 2 — 12 associados com pagamento `cancelado` → movidos para seção `cancelados`.**

Os 12 eram associados com `status=em_analise` e `etapa_atual=analise`, mas cujo registro de pagamento no módulo de tesouraria tinha `status=cancelado` e `paid_at=None` (nunca efetivado).

### Script de correção para produção

Executar no servidor de produção via Django shell (`python manage.py shell`):

```python
from django.apps import apps
from apps.associados.models import Associado
from apps.esteira.models import EsteiraItem
from apps.contratos.models import Contrato

Pagamento = apps.get_model('tesouraria', 'Pagamento')

# CPFs dos 12 associados com pagamento cancelado que estavam em novos_contratos
cpfs_cancelados = [
    '00774711302',  # ANA FERNANDA VIEIRA DA SILVA
    '02534091360',  # FRANCISCA DA CONCEIÇÃO SANTOS
    '07799918349',  # FRANCISCA DAS CHAGAS SOARES
    '34308350387',  # GEORGE AFONSO FELIX DE CARVALHO
    '37349368372',  # FRANCISCA MARLENE DA SILVA TEIXEIRA
    '39562360334',  # MARINALVA DA SILVA CARVALHO
    '47064056372',  # RITA DE CASSIA PEREIRA LIMA
    '49780115315',  # HELENA SOFIA CARVALHO SILVA
    '60337602395',  # VICENTE BRASIL DA SILVA NETO
    '66141931391',  # BRUNO LEONARDO MOURAO FERNANDES
    '77923006334',  # AISLAN WANDERSON DE SOUSA LIMA
    '93816863353',  # VANESSA SOARES NEGREIROS FARIAS
]

assoc_ids = list(
    Associado.objects.filter(cpf_cnpj__in=cpfs_cancelados, deleted_at__isnull=True)
    .values_list('id', flat=True)
)

# Verificação antes de aplicar
print('IDs encontrados:', assoc_ids)
print('Esperado: 12 | Encontrado:', len(assoc_ids))

# Aplicar normalização
a = Associado.objects.filter(id__in=assoc_ids).update(status='inativo')
e = EsteiraItem.objects.filter(associado_id__in=assoc_ids, deleted_at__isnull=True).update(
    etapa_atual='concluido', status='rejeitado'
)
c = Contrato.objects.filter(associado_id__in=assoc_ids, deleted_at__isnull=True).update(
    status='cancelado'
)

print(f'Associados atualizados: {a}')
print(f'EsteiraItems atualizados: {e}')
print(f'Contratos atualizados: {c}')
```

**Resultado esperado:**

```text
Associados atualizados: 12
EsteiraItems atualizados: 12
Contratos atualizados: 12
```

**Verificação pós-execução:**

```python
from apps.esteira.analise_services import AnaliseService
from django.contrib.auth import get_user_model

User = get_user_model()
u = User.objects.filter(is_superuser=True).first()

novos = AnaliseService.fila_queryset(secao='novos_contratos', user=u).count()
cancelados = AnaliseService.fila_queryset(secao='cancelados', user=u).count()
print('novos_contratos:', novos)   # esperado: 0
print('cancelados:', cancelados)   # esperado: >= 12
```

### Efeito

| Seção               | Antes              | Depois |
| ------------------- | ------------------ | ------ |
| `novos_contratos`   | 12 itens indevidos | 0      |
| `cancelados`        | 0                  | 12     |

### Arquivos alterados nesta sessão (pendentes de deploy)

- `backend/apps/esteira/serializers.py` — `EsteiraAssociadoCompatSerializer`: adicionado campo `status`
- `backend/apps/esteira/analise_services.py` — `novos_contratos`: guard para excluir `ativo/inadimplente/inativo`
- `apps/web/src/lib/api/client.ts` — `apiFetch`: tratamento explícito de 204/205 (sem falso erro)
- `apps/web/src/lib/api/types.ts` — `EsteiraItem.associado`: adicionado campo `status`
- `apps/web/src/app/(dashboard)/analise/page.tsx` — coluna "Status": exibe `associado.status` real
- `apps/web/src/components/auth/auth-guard.tsx` — loop infinito para usuário sem roles corrigido

---

## Padronização de status Associado ↔ Contrato (2026-04-14)

### Problema resolvido

Até esta data, o `Contrato.status` e o `Associado.status` podiam divergir silenciosamente. A partir de agora:

1. **Todo display usa o mapa canônico `STATUS_LABELS`** — labels em português sem dependência de capitalização automática de slug.
2. **Django signal garante sincronia em tempo real** — toda vez que `Associado.status` é salvo, o(s) contrato(s) ativo(s) do associado recebem o status correspondente.
3. **Script de normalização** corrige registros históricos divergentes, respeitando edições manuais via "Editor Avançado".

### Mapeamento canônico Associado → Contrato

| Associado.status | Contrato.status | Descrição                                       |
|------------------|-----------------|-------------------------------------------------|
| `cadastrado`     | `rascunho`      | Recém-cadastrado, contrato ainda em rascunho    |
| `importado`      | `rascunho`      | Importado do legado                             |
| `pendente`       | `em_analise`    | Aguardando revisão                              |
| `em_analise`     | `em_analise`    | Em análise pela esteira                         |
| `ativo`          | `ativo`         | Associado ativo                                 |
| `inadimplente`   | `ativo`         | Contrato ativo, associado com parcela em atraso |
| `inativo`        | `cancelado`     | Associado saiu / foi cancelado                  |

Contratos com `status = encerrado` nunca são sobrescritos pelo signal — têm ciclo de vida próprio.

### Arquivos alterados

- `apps/web/src/components/custom/status-badge.tsx` — `STATUS_LABELS`: mapa canônico + `resolveStatusLabel()` substituindo `capitalize + replace("_"," ")`
- `backend/apps/associados/signals.py` — **novo** — signal `post_save` que sincroniza `Contrato.status` quando `Associado.status` muda
- `backend/apps/associados/apps.py` — `ready()`: registra o signal

### Script de normalização para produção

Executar no servidor via `python manage.py shell` **antes** do deploy (ou imediatamente após):

```python
from django.db import transaction
from django.db.models import OuterRef, Subquery

from apps.associados.models import AdminOverrideEvent, Associado
from apps.contratos.models import Contrato

# ── Mapeamento canônico ──────────────────────────────────────────────────
ASSOC_TO_CTR = {
    'cadastrado':   'rascunho',
    'importado':    'rascunho',
    'pendente':     'em_analise',
    'em_analise':   'em_analise',
    'ativo':        'ativo',
    'inadimplente': 'ativo',
    'inativo':      'cancelado',
}

# IDs de contratos que foram editados manualmente via Editor Avançado
# (Scope=contrato) — esses NÃO devem ser sobrescritos.
contratos_editados_manualmente = set(
    AdminOverrideEvent.objects
    .filter(
        scope=AdminOverrideEvent.Scope.CONTRATO,
        deleted_at__isnull=True,
    )
    .values_list('contrato_id', flat=True)
)

total_updated = 0
skipped_manual = 0
skipped_encerrado = 0

with transaction.atomic():
    for assoc_status, ctr_status_esperado in ASSOC_TO_CTR.items():
        # Contratos cujo associado está com este status mas contrato diverge
        qs = (
            Contrato.objects
            .filter(
                associado__status=assoc_status,
                associado__deleted_at__isnull=True,
                deleted_at__isnull=True,
            )
            .exclude(status=ctr_status_esperado)
            .exclude(status=Contrato.Status.ENCERRADO)
            .exclude(id__in=contratos_editados_manualmente)
        )
        n = qs.update(status=ctr_status_esperado)
        total_updated += n
        print(f'  assoc={assoc_status!r:14} → ctr={ctr_status_esperado!r:12}  atualizados={n}')

    # Relatório de ignorados
    skipped_manual = (
        Contrato.objects
        .filter(id__in=contratos_editados_manualmente, deleted_at__isnull=True)
        .count()
    )
    skipped_encerrado = (
        Contrato.objects
        .filter(status=Contrato.Status.ENCERRADO, deleted_at__isnull=True)
        .count()
    )

print()
print(f'Total atualizados : {total_updated}')
print(f'Preservados (manual override) : {skipped_manual}')
print(f'Preservados (encerrado)       : {skipped_encerrado}')
```

**Verificação pós-execução:**

```python
# Deve retornar 0 — nenhum contrato divergente restante (exceto encerrados e editados)
from apps.associados.models import AdminOverrideEvent, Associado
from apps.contratos.models import Contrato

ASSOC_TO_CTR = {
    'cadastrado': 'rascunho', 'importado': 'rascunho',
    'pendente': 'em_analise', 'em_analise': 'em_analise',
    'ativo': 'ativo', 'inadimplente': 'ativo', 'inativo': 'cancelado',
}
editados = set(
    AdminOverrideEvent.objects
    .filter(scope=AdminOverrideEvent.Scope.CONTRATO, deleted_at__isnull=True)
    .values_list('contrato_id', flat=True)
)
divergentes = 0
for assoc_status, ctr_esperado in ASSOC_TO_CTR.items():
    n = (
        Contrato.objects
        .filter(associado__status=assoc_status, associado__deleted_at__isnull=True, deleted_at__isnull=True)
        .exclude(status=ctr_esperado)
        .exclude(status='encerrado')
        .exclude(id__in=editados)
        .count()
    )
    if n:
        print(f'  DIVERGENTE  assoc={assoc_status!r}  ctr≠{ctr_esperado!r}  count={n}')
    divergentes += n

print('Divergentes restantes:', divergentes)  # esperado: 0
```

---

## Fila do analista, dashboard e novos contratos (2026-04-14)

### Problemas resolvidos

Três correções aplicadas em sequência nesta sessão:

1. **`apto_a_renovar` aparecia na rota "Contratos para Renovação"** — itens ainda não submetidos pelo agente vazavam para a fila do analista.
2. **Cards KPI redundantes no dashboard do analista** — `efetivados` e `cancelados` não têm ação disponível para o analista; `enviado_coordenação` ficou mas os outros dois foram removidos para não poluir o painel.
3. **Novos contratos sem documentação excluídos indevidamente** — cadastros sem documentos enviados ou com `doc_issue` aberta desapareciam de "Novos Contratos", obrigando o analista a buscá-los em "Pendências".

### 1 — Fila Contratos para Renovação

**Arquivo:** `backend/apps/refinanciamento/views.py`

`AnalistaRefinanciamentoViewSet.get_queryset()` passa a usar a constante `ANALISTA_STATUSES`:

| Status                       | Incluso | Motivo                                               |
|------------------------------|---------|------------------------------------------------------|
| `em_analise_renovacao`       | ✅      | Submetido para análise                               |
| `pendente_termo_analista`    | ✅      | Aguardando ação do analista                          |
| `pendente_termo_agente`      | ✅      | Aguardando assinatura do agente (analista precisa ver) |
| `aprovado_analise_renovacao` | ✅      | Aprovado na análise, aguardando coordenação          |
| `apto_a_renovar`             | ❌      | Não submetido ainda — agente não enviou              |
| `pendente_apto`              | ❌      | Pré-submissão                                        |
| `solicitado`                 | ❌      | Legado pré-submissão                                 |
| qualquer outro               | ❌      | Não relevante para o analista                        |

Adicionado também `deleted_at__isnull=True` explícito no filtro como salvaguarda.

### 2 — Dashboard de análise — KPIs

**Arquivo:** `apps/web/src/app/(dashboard)/analise/page.tsx`

| KPI | Antes | Depois |
|-----|-------|--------|
| Novos Contratos | ✅ | ✅ |
| Ver Todos | ✅ | ✅ |
| Pendências | ✅ | ✅ |
| Pendências Corrigidas | ✅ | ✅ |
| Enviado Tesouraria | ✅ | ✅ |
| Enviado Coordenação | ✅ | ✅ |
| **Efetivados** | ✅ | ❌ removido |
| **Cancelados** | ✅ | ❌ removido |

Grid ajustado: `xl:grid-cols-4` → `xl:grid-cols-5` para acomodar os 6 KPIs restantes sem overflow.

### 3 — Regra de Novos Contratos

**Arquivo:** `backend/apps/esteira/analise_services.py`

Duas condições de exclusão removidas da seção `novos_contratos`:

| Condição removida | Motivo |
|-------------------|--------|
| `has_open_doc_issue=True` | Issue documental aberta não indica que o analista já atuou — o contrato ainda é novo |
| `has_documents=False AND has_any_reupload=False` | Cadastro sem documentos ainda é um novo contrato válido para triagem inicial |

Condições mantidas (indicam que o item já foi trabalhado):

| Condição mantida | Significado |
|------------------|-------------|
| `has_open_pendencia=True` | Analista já abriu uma pendência — não é mais "novo" |
| `has_received_reupload=True` | Associado reenviou documentos — está no ciclo de correção |
| `resolved_pendencias_count > 0` | Pendência já foi resolvida — está no ciclo de correção |
| `associado.status IN (ativo, inadimplente, inativo)` | Associado já efetivado ou cancelado |

### Arquivos alterados nesta sessão

- `backend/apps/refinanciamento/views.py` — `AnalistaRefinanciamentoViewSet`: constante `ANALISTA_STATUSES`, exclude `apto_a_renovar`, `deleted_at` explícito
- `apps/web/src/app/(dashboard)/analise/page.tsx` — remove `efetivados` e `cancelados` de `FILA_SECTIONS`; grid `xl:grid-cols-5`
- `backend/apps/esteira/analise_services.py` — `novos_contratos`: remove exclusão por `has_open_doc_issue` e `has_documents=False`
