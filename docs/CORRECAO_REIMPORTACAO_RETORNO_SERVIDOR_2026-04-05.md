# Correção da Reimportação de Arquivos Retorno no Servidor

Data: 2026-04-05

## Resumo executivo

O problema identificado não estava no parser do `.txt` em si, mas no comportamento de reimportação quando o servidor já possuía lançamentos em `PagamentoMensalidade` para a mesma combinação de `CPF + competência`.

Antes desta correção, ao reenviar um arquivo retorno de uma competência já existente:

- o sistema encontrava o `PagamentoMensalidade` já salvo;
- tratava o item como duplicado;
- mas não atualizava os campos principais vindos do novo arquivo retorno;
- com isso, permaneciam no banco status, valor, vínculo e origem de arquivo antigos ou incorretos.

Na prática, isso fazia o financeiro do servidor divergir do local mesmo com o mesmo arquivo, porque o cálculo financeiro não lê o `.txt` puro: ele lê o estado consolidado de `PagamentoMensalidade` no banco.

## Sintoma observado

No servidor, ao importar novamente os arquivos retorno de `12/2025`, `01/2026` e `02/2026`, o valor recebido podia ficar diferente do local mesmo usando o mesmo arquivo.

O motivo é que o valor financeiro exibido é calculado sobre os registros atuais de `PagamentoMensalidade`, somando:

- retorno efetivado;
- baixas manuais;
- snapshots legados;
- relatório manual da competência, quando existir.

Referências de código:

- [services.py](/mnt/d/apps/abasev2/abasev2/backend/apps/importacao/services.py#L477)
- [financeiro.py](/mnt/d/apps/abasev2/abasev2/backend/apps/importacao/financeiro.py#L75)
- [financeiro.py](/mnt/d/apps/abasev2/abasev2/backend/apps/importacao/financeiro.py#L232)
- [legacy.py](/mnt/d/apps/abasev2/abasev2/backend/apps/importacao/legacy.py#L242)

## Causa raiz

O branch de duplicado do upsert em `PagamentoMensalidade` fazia apenas:

- backfill de associado quando faltava vínculo;
- aplicação de snapshot manual legado em alguns casos;
- abertura de duplicidade financeira para conflito manual.

Mas ele não atualizava os campos principais do retorno já existente, como:

- `status_code`
- `valor`
- `matricula`
- `orgao_pagto`
- `nome_relatorio`
- `import_uuid`
- `source_file_path`

Resultado:

- uma reimportação não corrigia um lançamento ruim já persistido;
- o servidor continuava contabilizando com base no registro antigo;
- por isso o valor financeiro podia divergir do local.

## Correção aplicada no código

Foi implementado ajuste em [services.py](/mnt/d/apps/abasev2/abasev2/backend/apps/importacao/services.py):

- criação do helper `_sync_pagamento_from_return(...)` para sincronizar os campos do retorno no `PagamentoMensalidade` existente;
- na reimportação do mesmo `CPF + competência`, o registro existente agora é atualizado com os dados do arquivo retorno mais recente;
- quando existir uma baixa manual legada do mesmo mês, com `status=1` no retorno e mesmo valor, o lançamento é promovido automaticamente para retorno, limpando o contexto manual legado;
- quando houver divergência real de valor/status, o item continua indo para a esteira de duplicidade financeira.

## O que esta correção resolve

- Reimportar o mesmo mês no servidor passa a corrigir registros antigos do retorno em vez de ignorá-los.
- O financeiro da competência passa a refletir o arquivo reimportado, desde que a divergência esteja em lançamentos do próprio retorno.
- Casos de baixa manual legada idêntica ao retorno deixam de inflar conflito desnecessário.

## O que esta correção não resolve

- Não corrige automaticamente divergências de regra de negócio que não dependem da reimportação.
- Não substitui análise específica de `11/2025` caso exista regra adicional naquele mês.
- Não sobrescreve conflito manual real com divergência de valor; nesses casos a duplicidade continua correta.

## Estratégia de correção no servidor

Deploy do código sozinho não corrige os dados já salvos. Para corrigir o servidor, é necessário:

1. publicar esta atualização do backend;
2. reiniciar os serviços do backend;
3. reimportar as competências afetadas em ordem cronológica.

## Procedimento recomendado

### 1. Backup antes da correção

Fazer backup do banco e da mídia antes do deploy e antes da nova reimportação.

### 2. Publicar a atualização

Atualizar o código do backend com esta correção e reiniciar:

```bash
docker compose build backend celery
docker compose up -d backend celery
```

Se o deploy no servidor não recompila imagens, aplicar o procedimento equivalente usado na operação atual.

### 3. Reimportar os arquivos retorno

Reimportar as competências afetadas em ordem cronológica:

1. `2025-12`
2. `2026-01`
3. `2026-02`

Se também houver necessidade operacional, incluir `2025-10` e `2025-11` antes delas.

Pode ser feito pela tela de importação ou pelo comando de reimportação staged, se os arquivos já estiverem organizados em manifesto.

Exemplo com staged files:

```bash
docker compose exec -T backend python manage.py reimport_staged_return_files \
  --staging-dir /caminho/do/staging \
  --execute
```

Observação:

- não é necessário rodar um rebuild manual de ciclos como etapa operacional separada desta correção;
- a correção é focada na importação e na atualização de `PagamentoMensalidade`.

## Como validar após o deploy

### Validação funcional

Após reimportar, validar:

- histórico em `/importacao` com os arquivos concluídos;
- resumo financeiro da competência;
- valor recebido por competência;
- ausência de explosão artificial de duplicidades para casos idênticos ao retorno.

### Validação técnica por shell

Exemplo para conferir o resumo financeiro de uma competência:

```bash
docker compose exec -T backend python manage.py shell -c "
from datetime import date
from apps.importacao.financeiro import build_financeiro_resumo
print(build_financeiro_resumo(competencia=date(2025, 12, 1)))
"
```

Exemplo para conferir quantos pagamentos existem por competência:

```bash
docker compose exec -T backend python manage.py shell -c "
from django.db.models import Count
from apps.importacao.models import PagamentoMensalidade
print(list(
    PagamentoMensalidade.objects
    .values('referencia_month')
    .annotate(total=Count('id'))
    .order_by('referencia_month')
))
"
```

## Testes de regressão adicionados

Cobertura adicionada em [test_services.py](/mnt/d/apps/abasev2/abasev2/backend/apps/importacao/tests/test_services.py):

- reimportação do mesmo mês atualiza o `PagamentoMensalidade` existente;
- baixa manual legada do mesmo valor é promovida para retorno efetivado;
- baixa manual com valor divergente continua indo para duplicidade.

## Conclusão

O problema principal do servidor era stateful: a reimportação não convergia o dado já salvo.

Com esta correção:

- o backend passa a reaproveitar e atualizar corretamente o lançamento do mês;
- o deploy corrige o comportamento futuro da reimportação;
- a correção efetiva dos valores no servidor acontece depois da reimportação das competências afetadas.
