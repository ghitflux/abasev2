# Patch 2026-04-16: Alinhamento de Renovação

## Objetivo

Alinhar contagem e classificação de renovação entre:

- `Tesouraria > Contratos para Renovação`
- `Coordenação > Refinanciados`
- `Dashboard > Resumo mensal da associação`
- status do associado enviado para web/app

Também corrige `efetivado` fantasma: refinanciamento marcado como `efetivado` sem `executado_em`, sem `data_ativacao_ciclo` e sem `ciclo_destino`.

## Documento complementar

Para os ajustes operacionais da rota `Aptos a renovar`, exportação, competência
default da fila e scripts pós-deploy, ver também:

- [2026-04-16-aptos-renovacao-operacional.md](/mnt/d/apps/abasev2/abasev2/docs/patches/2026-04-16-aptos-renovacao-operacional.md)

## Mudanças incluídas

- competência corrente de renovação acompanha pelo menos o mês atual
- aptidão à renovação usa a régua real da competência
- `efetivado` só conta como efetivado real quando houve materialização da tesouraria
- rebuild de ciclos deixa de reaproveitar `efetivado` fantasma
- dashboard passa a contar renovação por refinanciamento efetivado real
- tela da tesouraria passa a abrir com recorte do ano corrente

## Deploy

No servidor:

```bash
cd /app
git pull
docker compose build backend web
docker compose up -d backend web
```

## Auditoria pré-correção

Rodar antes de aplicar a limpeza:

```bash
docker compose exec backend python manage.py repair_renewal_alignment --competencia 2026-04
```

Saídas esperadas:

- lista de `Refinanciamentos efetivados sem materialização`
- resumo com:
  - `tesouraria.efetivados_ano`
  - `coordenacao.total_ano`
  - `coordenacao.renovados_ano`
  - `coordenacao.em_processo_ano`
  - `dashboard.renovacoes_associado_mes`

## Aplicação da correção

```bash
docker compose exec backend python manage.py repair_renewal_alignment --apply --competencia 2026-04
```

O comando:

- reclassifica `efetivado` fantasma para `aprovado_para_renovacao` ou `apto_a_renovar`
- reconstrói o ciclo do contrato afetado
- sincroniza o status-mãe do associado

## Validação pós-deploy

### 1. Validar backend

```bash
docker compose exec backend python manage.py repair_renewal_alignment --competencia 2026-04
```

Esperado:

- `Refinanciamentos efetivados sem materialização: 0`

### 2. Validar tesouraria

Abrir `Tesouraria > Contratos para Renovação`.

Conferir:

- card `Efetivadas` no ano corrente
- pendentes coerentes com `aprovado_para_renovacao`
- casos corrigidos:
  - `32784066304` em `aprovado_para_renovacao`
  - `24053198372` em `aprovado_para_renovacao`

### 3. Validar coordenação

Abrir `Coordenação > Refinanciados`.

Conferir:

- `Renovados` = `efetivados` reais do ano
- `Em processo` = aprovados/aguardando do ano

### 4. Validar dashboard

Abrir `Dashboard > Resumo mensal da associação`.

Conferir:

- coluna `Renovações` usando refinanciamento efetivado real
- detalhe do metric `trend:renovacoes:YYYY-MM` compatível com os efetivados reais daquele mês

### 5. Validar associados críticos

Conferir no admin/web/app:

- `07937679387` `apto_a_renovar`
- `13019414334` `apto_a_renovar`
- `03028801353` `apto_a_renovar`
- `32784066304` `aprovado_para_renovacao`
- `24053198372` `aprovado_para_renovacao`
- `44623577368` sem `efetivado` fantasma
- `01843564319` sem `efetivado` fantasma

## Rollback de dados

Se precisar interromper após o deploy mas antes da aplicação:

- não rodar `--apply`

Se a correção já foi aplicada e precisar reavaliar:

- restaurar backup do banco
- ou revisar manualmente os refinanciamentos alterados pelo comando a partir do output

## Observação

O card de tesouraria e a coordenação podem continuar diferentes por desenho quando o card de coordenação mostra `total` e não apenas `renovados`. O alinhamento desta patch garante que o número de `efetivados/renovados reais` use a mesma fonte.
