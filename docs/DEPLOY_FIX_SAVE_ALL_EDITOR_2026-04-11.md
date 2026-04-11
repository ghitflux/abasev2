# Deploy: Fix Save-All Editor Admin — 2026-04-11

## Resumo

Correção de erro 500 no endpoint `POST /api/v1/admin-overrides/associados/{id}/save-all/`
que impedia salvar edições no editor avançado do admin (ex: associado 26 — Maria do Amparo).

---

## Commits Deployados

| Commit | Descrição |
|--------|-----------|
| `f526e9d` | feat(associados): melhorias no editor de contratos, overrides e projeções |
| `a257943` | fix(client): add explicit return type to extractApiErrorMessage to fix TS build error |
| `036797c` | fix(admin-override): evitar IntegrityError na renumeração temporária (tentativa 1 — incorreta) |
| `5e6dc58` | fix(admin-override): usar max+offset como numero temporario para evitar out-of-range (**fix definitivo**) |

---

## Causa Raiz

### Problema na renumeração temporária de parcelas/ciclos

O método `apply_cycle_layout_override` em `admin_override_service.py` faz uma
renumeração temporária antes de atribuir os números finais, para evitar colisão
na constraint `UNIQUE (ciclo_id, numero)` da tabela `contratos_parcela`.

**Código original (quebrado):**
```python
for index, parcela in enumerate(existing_parcela_list, start=1):
    temporary_number = 1000 + index  # PROBLEMA: colisão quando parcelas de mesmo ciclo
```

Dois problemas encadeados foram encontrados e corrigidos:

**Tentativa 1 — `100000 + id` (commit 036797c):**
- Resolvia a colisão de constraint ✅
- Mas: campo `numero` é `smallint unsigned` (máx 65535), e `100000 + id` estoura para qualquer ID > 40 ❌

**Fix definitivo — `max_numero_existente + 1 + index` (commit 5e6dc58):**
```python
if existing_parcela_list:
    max_parcela_numero = max(p.numero for p in existing_parcela_list)
    for index, parcela in enumerate(existing_parcela_list):
        temporary_number = max_parcela_numero + 1 + index
```
- Garante unicidade global (sequencial, acima do máximo atual) ✅
- Nunca estoura o tipo (dados reais: máx ~1006, count ~9, total ~1015 << 65535) ✅

---

## Problema Adicional de Deploy

O fix do commit `036797c` **não foi aplicado** na primeira tentativa porque o container
foi apenas **reiniciado** (`docker restart`) e não **rebuilado**. O container continuava
com a imagem Docker antiga.

**Lição reforçada:** após qualquer push de código, SEMPRE rebuildar com `--no-cache`:
```bash
docker compose -f docker-compose.prod.yml --env-file /opt/ABASE/env/.env.production \
  build --no-cache backend celery
docker compose -f docker-compose.prod.yml --env-file /opt/ABASE/env/.env.production \
  up -d --force-recreate backend celery
```

---

## Arquivos Alterados

- `backend/apps/associados/admin_override_service.py` — renumeração temporária (método `apply_cycle_layout_override`)
- `apps/web/src/lib/api/client.ts` — tipo de retorno explícito em `extractApiErrorMessage` (build TS produção)
- `apps/web/src/components/associados/admin-contract-editor.tsx` — melhorias editor
- `apps/web/src/components/associados/associado-form.tsx` — melhorias formulário
- `apps/web/src/app/(dashboard)/associados/[id]/page.tsx` — melhorias página
- `backend/apps/contratos/cycle_projection.py` — melhorias projeção
- `backend/apps/contratos/manual_cycle_layout_repair.py` — melhorias repair
- `backend/apps/contratos/special_references.py` — melhorias referências
- `backend/apps/associados/admin_override_views.py` — melhorias views

---

## Validação

Reprodução e confirmação do fix via Django shell no servidor de produção:
```
FUNCIONOU - operacao valida, rollback preventivo aplicado
```
(O único erro restante no teste manual foi `realizado_por_id cannot be null`,
esperado pois o teste passa `user=None` — na requisição real o usuário autenticado é fornecido.)
