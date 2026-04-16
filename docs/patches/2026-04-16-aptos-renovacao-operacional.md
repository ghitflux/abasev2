# Patch 2026-04-16: Aptos a Renovar, Esteira de Renovacao e Correcao Pos-Deploy

## Contexto

Este patch consolida os ajustes feitos entre `Tesouraria > Contratos para Renovacao`,
`Cadastros > Aptos a renovar`, `Analise > Esteira de Renovacao` e o alinhamento
do status persistido do associado.

Na data de validacao deste patch, `16/04/2026`, a competencia operacional atual de
renovacao e `2026-04`.

## Problemas corrigidos

- a aba `Aptos a renovar` mostrava contratos fora da fila real
- o card `Aptos a renovar` podia divergir da tabela
- a lista apta usava uma origem diferente do resumo e da esteira
- contratos ja enviados para renovacao ainda podiam aparecer em `Aptos`
- contratos ja renovados em abril precisavam ficar fora da fila apta
- havia drift entre a fila real e `Associado.status = apto_a_renovar`
- a exportacao da rota era limitada e nao permitia escolher periodo/agente
- o endpoint `renovacao-ciclos` podia cair na `ultima importacao concluida`,
  em vez da competencia operacional de renovacao

## O que foi alterado

### Backend

- [backend/apps/contratos/renovacao.py](/mnt/d/apps/abasev2/abasev2/backend/apps/contratos/renovacao.py)
  - `parse_competencia_query()` passou a usar `resolve_current_renewal_competencia()`
    como default, em vez da ultima importacao concluida
  - `RenovacaoCicloService.listar_detalhes()` recebeu filtros de:
    - `agente_id`
    - `data_inicio`
    - `data_fim`
  - a listagem apta passou a excluir contratos cujo
    `build_contract_cycle_projection(...).status_renovacao` nao seja
    `apto_a_renovar`
  - isso retira da aba apta quem ja entrou em fluxo ou ja foi renovado

- [backend/apps/contratos/views.py](/mnt/d/apps/abasev2/abasev2/backend/apps/contratos/views.py)
  - `RenovacaoCicloViewSet.list()` passou a aceitar:
    - `competencia`
    - `search`
    - `agente`
    - `data_inicio`
    - `data_fim`
  - `RenovacaoCicloViewSet.exportar()` usa o mesmo recorte da lista
  - `ContratoViewSet.renovacao_resumo()` foi alinhado para ler o recorte operacional
    da renovacao
  - a permissao da fila operacional ficou disponivel para a operacao

- [backend/apps/contratos/management/commands/repair_renewal_alignment.py](/mnt/d/apps/abasev2/abasev2/backend/apps/contratos/management/commands/repair_renewal_alignment.py)
  - audita e corrige:
    - `efetivado` fantasma
    - associado com `status=apto_a_renovar` fora da fila real
    - associado apto na fila real com status persistido divergente

### Frontend

- [apps/web/src/app/(dashboard)/agentes/refinanciados/page.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/app/(dashboard)/agentes/refinanciados/page.tsx)
  - a aba `Aptos a renovar` passou a consumir `renovacao-ciclos`
  - a tabela apta deixou de depender de `contratos?status_renovacao=apto_a_renovar`
  - o card `Aptos a renovar` usa o `count` da mesma lista exibida na tela
  - `Solicitacoes e historico` continua lendo `refinanciamentos`
  - o envio para renovacao leva o item para o historico e ele sai da fila apta
  - exportacao ficou completa, com selecao de:
    - periodo
    - agente
    - colunas
  - a tabela apta foi adaptada para mostrar:
    - associado
    - agente responsavel
    - ciclo que gerou o apto
    - valores
    - acoes operacionais

- [apps/web/src/lib/api/types.ts](/mnt/d/apps/abasev2/abasev2/apps/web/src/lib/api/types.ts)
  - adicionados os tipos do payload operacional de `RenovacaoCicloItem`

- [apps/web/src/app/(dashboard)/agentes/refinanciados/page.test.tsx](/mnt/d/apps/abasev2/abasev2/apps/web/src/app/(dashboard)/agentes/refinanciados/page.test.tsx)
  - cobertura de:
    - filtros da aba apta
    - exportacao usando a fila operacional
    - comportamento por perfil

## Resultado validado

### Estado final conferido em `16/04/2026`

- competencia operacional atual: `2026-04-01`
- fila real `Aptos a renovar` em abril/2026: `90`
- associados com `status=apto_a_renovar` persistido: `90`
- drift restante entre fila real e status persistido: `0`
- `Refinanciamentos efetivados sem materializacao`: `0`

### Resumo de alinhamento auditado

- `tesouraria.efetivados_ano = 260`
- `coordenacao.total_ano = 262`
- `coordenacao.renovados_ano = 260`
- `coordenacao.em_processo_ano = 2`
- `dashboard.renovacoes_associado_mes = 0`

## Motivo do erro de `2 aptos`

O card/tabela da rota apta estava consultando `renovacao-ciclos` sem competencia
explicita. O backend usava como default a `ultima importacao concluida`, enquanto
o restante do fluxo de renovacao ja estava operando na competencia real de
renovacao, `abril/2026`.

Isso fazia a mesma tela misturar meses diferentes:

- resumo/KPIs usando a competencia operacional atual
- lista apta usando o fallback da ultima importacao

Depois da correcao, o default do endpoint ficou alinhado com
`resolve_current_renewal_competencia()`.

## Scripts para rodar no servidor apos deploy

Os scripts abaixo foram adicionados ao repositório:

- [scripts/audit_renewal_alignment_server.sh](/mnt/d/apps/abasev2/abasev2/scripts/audit_renewal_alignment_server.sh)
- [scripts/post_deploy_renewal_alignment_server.sh](/mnt/d/apps/abasev2/abasev2/scripts/post_deploy_renewal_alignment_server.sh)

Eles assumem:

- execucao a partir da raiz do projeto
- containers `backend` e `web` ja levantados via `docker compose`

### 1. Auditoria simples

```bash
bash scripts/audit_renewal_alignment_server.sh 2026-04
```

O script:

- executa `repair_renewal_alignment --competencia 2026-04`
- imprime `queue_apto` e `persisted_apto`
- roda `python manage.py check`

### 2. Correcao pos-deploy

```bash
bash scripts/post_deploy_renewal_alignment_server.sh 2026-04
```

O script:

- aplica migracoes pendentes
- faz auditoria antes da correcao
- roda `repair_renewal_alignment --apply --competencia 2026-04`
- roda auditoria depois da correcao
- imprime:
  - `queue_apto`
  - `persisted_apto`

## Passo a passo recomendado no servidor

### Deploy

```bash
cd /app
git pull
docker compose build backend web
docker compose up -d backend web
```

### Auditoria antes da correcao

```bash
bash scripts/audit_renewal_alignment_server.sh 2026-04
```

### Aplicacao da correcao

```bash
bash scripts/post_deploy_renewal_alignment_server.sh 2026-04
```

### Reinicio final

```bash
docker compose restart backend web
```

## Validacao manual pos-deploy

### 1. Aptos a renovar

Abrir `Cadastros > Aptos a renovar`.

Conferir:

- card `Aptos a renovar` igual ao total da tabela
- quem ja entrou em fluxo nao aparece em `Aptos`
- quem ja foi enviado para renovacao aparece em `Solicitacoes e historico`
- exportacao oferece:
  - periodo
  - agente

### 2. Tesouraria

Abrir `Tesouraria > Contratos para Renovacao`.

Conferir:

- quem ja renovou em `abril/2026` permanece fora da fila apta
- contratos efetivados seguem apenas em tesouraria/historicos

### 3. Associados

Conferir no admin/app/web:

- nenhum associado fica com `status=apto_a_renovar` fora da fila real
- nenhum contrato ja efetivado volta para `Aptos`
- nenhum contrato em `pendente_termo_agente` fica visivel em `Aptos`

## Comandos avulsos uteis no servidor

### Auditoria direta do comando principal

```bash
docker compose exec -T backend python manage.py repair_renewal_alignment --competencia 2026-04
```

### Aplicacao direta do comando principal

```bash
docker compose exec -T backend python manage.py repair_renewal_alignment --apply --competencia 2026-04
```

### Conferir fila apta real x status persistido

```bash
docker compose exec -T backend python manage.py shell -c "
from datetime import date
from apps.associados.models import Associado
from apps.contratos.renovacao import RenovacaoCicloService

competencia = date.fromisoformat('2026-04-01')
queue_rows = RenovacaoCicloService.listar_detalhes(
    competencia=competencia,
    status='apto_a_renovar',
)
print({
    'queue_apto': len(queue_rows),
    'persisted_apto': Associado.objects.filter(status='apto_a_renovar').count(),
})
"
```

## Observacao operacional

No estado final validado deste patch, a fila real apta de `abril/2026` e `90`.
Se a interface exibir outro total apos o deploy:

- limpar cache do navegador com `Ctrl+Shift+R`
- repetir a auditoria
- repetir a correcao pos-deploy
- confirmar que `queue_apto` e `persisted_apto` continuam iguais
