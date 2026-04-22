# Patch 2026-04-22: Correcao do Fluxo de Inativacao de Associado

## Contexto

Foram identificados quatro problemas no fluxo de inativacao de associados:

1. **"Inativo passivel de renovacao" nao alterava o status** — o mapeamento
   apontava para `APTO_A_RENOVAR`, o mesmo status que associados ativos com
   contrato elegivel ja tinham. A inativacao retornava sucesso mas nada mudava.

2. **Editor avancado nao atualizava apos inativacao** — o `onSuccess` da
   mutation nao invalidava a query `admin-associado-editor`, entao o botao
   "Reverter inativacao" nao aparecia imediatamente no painel do editor
   avancado; o usuario precisava fechar e reabrir o toggle manualmente.

3. **Associado `inadimplente` exibia botao "Inativar" em vez de "Reativar"** —
   a condicao verificava apenas `status === "inativo"`, ignorando que
   `inadimplente` tambem e um estado inativo.

4. **Motivo de inativacao mudava o status** — o campo `status_destino` era
   usado para escolher entre `INATIVO`, `INADIMPLENTE` e `APTO_A_RENOVAR`.
   A regra correta e: inativacao sempre resulta em `INATIVO`, independente do
   motivo; o motivo e apenas metadado registrado no evento de historico.

## Arquivos alterados

- [backend/apps/associados/services.py](../../backend/apps/associados/services.py)
- [apps/web/src/app/(dashboard)/associados/[id]/page.tsx](../../apps/web/src/app/(dashboard)/associados/[id]/page.tsx)

## Regras aplicadas

### Backend — `services.py`

`INACTIVATION_STATUS_TARGETS` foi substituido por `INACTIVATION_MOTIVOS`:

```python
INACTIVATION_MOTIVOS = {
    "inativo":                  "inativo",
    "inativo_inadimplente":     "inadimplente",
    "inativo_passivel_renovacao": "passivel de renovacao",
    "inativo_a_pedido":         "a pedido do associado",
    "inativo_falecimento":      "falecimento",
    "inativo_outros":           "outros motivos",
}
```

`inativar_associado` agora:
- Valida o `status_destino` contra `INACTIVATION_MOTIVOS`
- Sempre define `target_status = Associado.Status.INATIVO`
- Usa o label do motivo apenas para gravar o texto descritivo no evento

### Frontend — `page.tsx`

**Opcoes do dropdown expandidas (5 motivos):**

| Valor | Label |
|-------|-------|
| `inativo_inadimplente` | Inadimplente |
| `inativo_passivel_renovacao` | Passivel de renovacao |
| `inativo_a_pedido` | A pedido do associado |
| `inativo_falecimento` | Falecimento |
| `inativo_outros` | Outros motivos |

**Botoes de acao corrigidos:**

```tsx
// Antes
associado.status === "inativo"   → mostra "Iniciar reativacao"
associado.status !== "inativo"   → mostra "Inativar associado"

// Depois
["inativo", "inadimplente"].includes(status)  → mostra "Iniciar reativacao"
!["inativo", "inadimplente"].includes(status) → mostra "Inativar associado"
```

**Invalidacao do editor apos inativacao:**

```tsx
onSuccess: async (payload) => {
  // ...alem de invalidar ["associados"] e ["contratos"], agora tambem:
  await queryClient.invalidateQueries({ queryKey: ["admin-associado-editor", associadoId] });
  await queryClient.invalidateQueries({ queryKey: ["admin-associado-history", associadoId] });
}
```

## Commits

| Hash | Descricao |
|------|-----------|
| `d301fc3` | fix: inativacao passivel_renovacao usa INATIVO e invalida editor apos inativar |
| `c861fae` | fix: inadimplente tambem eh estado inativo — exibe reativar, esconde inativar |
| `c8c316e` | feat: inativacao sempre resulta em INATIVO com motivo flexivel |

## Sem migracao

Este patch nao adiciona nem altera modelos. Nenhum `manage.py migrate`
necessario.

## Validacao local executada

### 1. Check do backend no container

```bash
docker compose exec -T backend python manage.py check
```

Resultado: `System check identified no issues (0 silenced).`

### 2. Sanidade de diff

```bash
python -m py_compile backend/apps/associados/services.py
git diff --check -- backend/apps/associados/services.py
```

Resultado: sem erros de sintaxe ou whitespace.

## Deploy seguro no servidor

### Sequencia executada

```bash
cd /opt/ABASE/repo
git pull --ff-only origin abaseprod
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml build --no-cache backend celery frontend
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml up -d --force-recreate backend celery frontend
docker compose -p abase --env-file /opt/ABASE/env/.env.production \
  -f deploy/hostinger/docker-compose.prod.yml exec -T backend python manage.py check
```

Resultado: todos os 6 containers `healthy`, `check` com 0 issues.

## Comportamento esperado apos o patch

- Qualquer motivo de inativacao define `associado.status = "inativo"`
- O motivo escolhido e gravado no evento de historico administrativo
- Associado com status `inativo` ou `inadimplente` exibe botao "Iniciar reativacao"
- Associado com status `ativo`, `apto_a_renovar` ou `cadastrado` exibe botao "Inativar associado"
- Apos inativar, o botao "Reverter inativacao" aparece imediatamente no editor avancado
  (sem necessidade de recarregar o toggle)

## Nota sobre "Reverter inativacao"

O botao so aparece dentro do painel azul do "Modo editor avancado"
(toggle no canto superior direito da pagina do associado). O reversal
restaura o status anterior sem abrir um novo fluxo de reativacao.
